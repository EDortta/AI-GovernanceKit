"""Evidence-based, review-first project adoption used by ``install-agents``."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import context_authoring
from .context_authoring import render_document
from .discover import run_discover
from .project_config import ProviderConfig, is_llm_eligible, load_project_config


@dataclass(frozen=True)
class AdoptionProposal:
    root: Path
    overview: str
    limits: str
    evidence: list[str]
    unresolved: list[str]
    llm_warning: "LlmEnrichmentWarning | None" = None

    def as_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "overview": self.overview,
            "limits": self.limits,
            "evidence": self.evidence,
            "unresolved": self.unresolved,
            "llm_warning": self.llm_warning.as_dict() if self.llm_warning else None,
        }


@dataclass(frozen=True)
class LlmEnrichmentWarning:
    provider: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "reason": self.reason}


def _primary_provider(root: Path) -> ProviderConfig | None:
    config = load_project_config(root)
    if config is None:
        return None
    for provider in config.providers:
        if is_llm_eligible(provider):
            return provider
    return None


def configured_adoption_provider(root: Path) -> ProviderConfig | None:
    """Return the eligible primary provider without invoking it."""
    return _primary_provider(root.resolve())


def provider_label(provider: ProviderConfig) -> str:
    """Render only the non-secret provider identity shown to an operator."""
    return f"{provider.name} / {provider.model}"


def _llm_failure_reason(error: RuntimeError) -> str:
    message = str(error)
    if message == "selected agent returned invalid evidence":
        return (
            "the response's evidence is not a valid non-empty list of unique text entries"
        )
    if message == "selected agent returned evidence outside the selected sources":
        return (
            "the response cited a file that was not among the approved project sources"
        )
    return message


def build_adoption_proposal(
    root: Path,
    *,
    enrich_with_llm: bool = False,
    on_top_level_directory: Callable[[Path], None] | None = None,
) -> AdoptionProposal:
    root = root.resolve()
    discovery = run_discover(root, on_top_level_directory)
    evidence = [*discovery.governance_files, *discovery.frameworks, *discovery.package_managers]
    stack = ", ".join([*discovery.frameworks, *discovery.languages]) or "not detected"
    commands = ", ".join(discovery.automation_commands) or "not detected"
    unresolved = ["deployment target"]
    llm_summary = ""
    llm_warning: LlmEnrichmentWarning | None = None
    provider = configured_adoption_provider(root)
    if provider and enrich_with_llm:
        # Reuse the hardened scope adapter: it confines sources, treats content as
        # data, validates returned JSON, and never persists credentials.
        from .agent_scope import propose_project_scope
        from .scope_conversation import load_required_reading
        sources, missing = load_required_reading(root)
        try:
            proposed = propose_project_scope(root, "llm-api", sources, provider=provider)
            llm_summary = proposed.summary
            evidence.extend(item for domain in proposed.domains for item in domain.evidence)
            unresolved.extend(proposed.questions)
        except RuntimeError as exc:
            llm_warning = LlmEnrichmentWarning(
                provider=provider_label(provider), reason=_llm_failure_reason(exc)
            )
        unresolved.extend(missing)
    # Bodies only. The document shape, the `## Metadata` block and — above all — the
    # readiness flag come from the one renderer both paths share. This function used to
    # write `- project_context_ready: yes` into the literal, three lines above the list
    # of things it had failed to determine.
    overview_body = "\n".join((
        "## Evidence-based proposal", "", f"- Project: {root.name}", f"- Detected stack: {stack}",
        f"- Automation: {commands}",
        *(("- LLM scope proposal: " + llm_summary,) if llm_summary else ()),
    ))
    limits_body = "\n".join((
        "## Accepted baseline", "", "- Never commit credentials, tokens, or local runtime state.",
        "- Preserve existing project-authored documentation during upgrades.",
        "- Review database, deployment, and compatibility changes before application.", "",
        "## Detected recommendations", "", f"- Validate with: {commands}.",
    ))
    overview = render_document("project_context_ready", overview_body, unresolved)
    limits = render_document("limits_ready", limits_body, [])
    return AdoptionProposal(root, overview, limits, evidence, unresolved, llm_warning)


@dataclass(frozen=True)
class AdoptionApplication:
    """What the deterministic path actually did, per document, and why.

    The flow used to report `written` alone, so an empty list printed as "existing
    project documents preserved" — which was a lie on a freshly seeded target, where
    the documents preserved were the KIT's own text, installed three steps earlier.
    """

    written: list[str]
    preserved: list[tuple[str, str]]  # (path, reason)

    @property
    def unconfirmed(self) -> list[str]:
        """Documents whose readiness flag is not `yes`, read from disk."""
        return list(self._unconfirmed)

    _unconfirmed: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "written": self.written,
            "preserved": [{"path": rel, "reason": why} for rel, why in self.preserved],
            "unconfirmed": self.unconfirmed,
        }


def apply_adoption_proposal(proposal: AdoptionProposal) -> AdoptionApplication:
    """Write the generated documents, replacing only what the kit itself put there.

    The gate used to be `f"{marker}: yes" in old` — an unanchored substring over the
    whole file. The template the installer seeds explains the flag in a sentence
    ("set `project_context_ready: yes` only after the file is accurate"), so the
    prose matched, the kit concluded the project had declared itself ready, and it
    wrote nothing while reporting success. `doctor._check_ready_flag` had the same
    defect and was anchored on 2026-08-04; the writer kept it for another eight days.

    Now the state comes from `classify_document`, the same anchored classifier the
    authoring flow uses, and there is no second opinion about what a flag means.
    """
    written: list[str] = []
    preserved: list[tuple[str, str]] = []
    for rel, content in (
        (context_authoring.OVERVIEW_REL, proposal.overview),
        (context_authoring.LIMITS_REL, proposal.limits),
    ):
        path = proposal.root / rel
        state = context_authoring.classify_document(proposal.root, rel)
        if state is context_authoring.DocState.READY:
            # An operator said so. The kit never retracts that.
            preserved.append((rel, "you already confirmed it ready"))
            continue
        if state is context_authoring.DocState.AUTHORED:
            preserved.append((rel, "you authored it — `author-context` reviews, never rewrites"))
            continue
        if state is context_authoring.DocState.TEMPLATE:
            old = path.read_text(encoding="utf-8", errors="replace")
            if not context_authoring.is_kit_authored(old):
                # Short, hand-written, and therefore indistinguishable from a template
                # by length alone. This is the protection the old `marker not in old`
                # branch bought, kept deliberately.
                preserved.append((rel, "you wrote it — too short to classify, so left alone"))
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)

    # Read the verdict off disk, never off what this function believes it did.
    unconfirmed = tuple(
        rel for rel in (context_authoring.OVERVIEW_REL, context_authoring.LIMITS_REL)
        if context_authoring.classify_document(proposal.root, rel)
        is not context_authoring.DocState.READY
    )
    return AdoptionApplication(written, preserved, _unconfirmed=unconfirmed)


def detect_project_drift(
    root: Path, *, on_top_level_directory: Callable[[Path], None] | None = None
) -> list[str]:
    """Report new observable project facts without rewriting accepted policy."""
    root = root.resolve()
    accepted = load_project_config(root)
    if accepted is None:
        return []
    discovered = run_discover(root, on_top_level_directory)
    drift: list[str] = []
    for label, current, recorded in (
        ("framework", set(discovered.frameworks), set(accepted.frameworks)),
        ("language", set(discovered.languages), set(accepted.languages)),
        ("package manager", set(discovered.package_managers), set(accepted.package_managers)),
    ):
        for value in sorted(current - recorded):
            drift.append(f"new {label} detected: {value}")
    return drift


def format_adoption_proposal(proposal: AdoptionProposal) -> str:
    lines = [
        "Project adoption proposal",
        f"Project: {proposal.root.name}",
        "Evidence: " + (", ".join(proposal.evidence) or "none"),
    ]
    if proposal.unresolved:
        lines.extend(["Open items:", *(f"  - {item}" for item in proposal.unresolved)])
    if proposal.llm_warning:
        lines.extend(
            [
                "",
                "[WARNING] LLM enrichment was skipped; no LLM result will be applied.",
                f"  Provider/model: {proposal.llm_warning.provider}",
                f"  Reason: {proposal.llm_warning.reason}.",
                "  Expected: each domain must cite selected sources as 'path: reason'.",
                "  How to proceed:",
                "    1. Review the deterministic proposal above; it remains safe to use.",
                "    2. Enter n at the next prompt to leave overview and limits unchanged.",
                "    3. Retry later; if it repeats, correct the configured primary provider/model before retrying.",
            ]
        )
    lines.append("Apply generated overview and limits?")
    return "\n".join(lines)


def format_provider_offer(root: Path, *, about_to_write: bool = False) -> str:
    """What the operator is choosing between, said once, at the moment they choose.

    A project without a configured provider used to reach the end of adoption without
    a single line about what it had missed: three separate code paths skipped the LLM
    in silence, so the operator saw a clean run and concluded this was all the kit
    could do. The `[MANDATORY]` policy in AI-Agents `credentials-operations.md` is that
    a project stays operable in manual mode — which is about not BLOCKING, not about
    staying quiet.

    The list is derived from `_llm_catalog.json`, so the models named here have an
    origin and a date rather than being three names somebody typed once.
    """
    from . import llm_catalog

    lines = [
        "No provider is configured for this project.",
        "The two context documents can be drafted from this project's README and the",
        "stack this kit detects, with an LLM. No source file is uploaded.",
        "",
    ]
    try:
        offers = llm_catalog.provider_offers()
        policy = llm_catalog.policy()
    except llm_catalog.CatalogError:
        offers, policy = [], ""
    if offers:
        lines.append("  OpenAI-compatible, with a free tier:")
        for offer in offers:
            free = f"{offer.free_models} free models" if offer.free_models else "account-dependent free tier"
            lines.append(f"    {offer.name:<11} {offer.signup_url}")
            detail = f"      {free}"
            if offer.model and offer.free_models:
                detail += f", widest: {offer.model}"
            lines.append(detail)
        if policy:
            lines.extend(["", f"  {policy}"])
        lines.append(f"  Catalog read on {llm_catalog.generated_at()[:10]}.")
    if about_to_write:
        # No prompt follows on this path — the run writes and exits. Offering to
        # "continue now" would describe a decision already taken, and put step 1 after
        # the write it is supposed to precede.
        lines.extend([
            "",
            "  This run continues without one: discovery is deterministic and needs no",
            "  key. Both documents are written below from detected evidence, with their",
            "  readiness flags left at `no` for you to confirm.",
            f"  To use an LLM next time: obtain a key, then run "
            f"'governancekit --root {root} config-session'.",
        ])
    else:
        lines.extend([
            "",
            "  How to proceed:",
            f"    1. Obtain a key, then run 'governancekit --root {root} config-session'.",
            "    2. Or continue now — discovery is deterministic and needs no key. The two",
            "       documents will be written from detected evidence, with their readiness",
            "       flags left at `no` for you to confirm.",
        ])
    return "\n".join(lines)


def format_readiness_warning(
    unconfirmed: list[str], root: Path, *, written: list[str] | None = None
) -> str:
    """The closing verdict when the Start Gate is still shut.

    Derived from the flags on disk, never from what the flow believes it did — the
    line it replaces printed "existing project documents preserved" over the kit's own
    boilerplate, because it reported an empty write list rather than a state.
    """
    if not unconfirmed:
        return ""
    # Say per document what actually happened to it. Asserting "written from detected
    # evidence" for every entry told the operator the kit had rewritten a file it had
    # said, four lines earlier, that it left alone — in the block designed to be the
    # last word. The state was read off disk and the cause was hardcoded.
    authored = set(written or ())

    def _line(rel: str) -> str:
        if rel in authored:
            return f"  {rel}: written from detected evidence, flag left at `no`"
        return f"  {rel}: yours, left untouched — its flag is not `yes`"

    return "\n".join([
        f"[WARNING] The Start Gate is shut: {len(unconfirmed)} document(s) are not confirmed ready.",
        *(_line(rel) for rel in unconfirmed),
        "  How to proceed:",
        "    1. Read them. They hold what discovery could prove; the rest is under",
        '       "Known unknowns".',
        "    2. Correct them and set the flag line yourself, or run",
        f"       'governancekit --root {root} author-context' to draft and confirm them.",
        f"    3. 'governancekit --root {root} doctor' reports the same two flags.",
    ])
