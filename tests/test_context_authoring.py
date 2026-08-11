from __future__ import annotations

import json
from pathlib import Path

import pytest

from governancekit import context_authoring as ca

_TEMPLATE = """# Agent Operational Limits

## Metadata

- limits_ready: no

When copied into a target project, the programmer must replace or extend these
limits with project-specific boundaries and set `limits_ready: yes` only after they
are accurate.
"""

_AUTHORED = """# Agent Operational Limits

## Metadata

- limits_ready: no

## Allowed

Agents may change the ingestion pipeline and its tests.
They may run the local test suite and the linter.
They may open issues and pull requests against development.

## Not allowed

Agents must never touch the billing reconciliation module.
Agents must never write to the production database.
Agents must never rotate credentials.
Deployment is a human decision, always.
Schema migrations require review by the data owner.
Third-party API contracts are frozen for this quarter.
"""


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ── the readiness flag is a line, never prose ─────────────────────────────────

def test_template_prose_is_not_a_ready_flag() -> None:
    assert not ca.flag_is_yes(_TEMPLATE, "limits_ready")


def test_metadata_line_is_a_ready_flag() -> None:
    assert ca.flag_is_yes("- limits_ready: yes\n", "limits_ready")
    assert ca.flag_is_yes("limits_ready:  yes  \n", "limits_ready")


# ── classification ────────────────────────────────────────────────────────────

def test_absent_document(tmp_path) -> None:
    assert ca.classify_document(tmp_path, ca.LIMITS_REL) is ca.DocState.ABSENT


def test_untouched_template_is_not_authored(tmp_path) -> None:
    _write(tmp_path, ca.LIMITS_REL, _TEMPLATE)
    assert ca.classify_document(tmp_path, ca.LIMITS_REL) is ca.DocState.TEMPLATE


def test_operator_written_document_is_authored(tmp_path) -> None:
    _write(tmp_path, ca.LIMITS_REL, _AUTHORED)
    assert ca.classify_document(tmp_path, ca.LIMITS_REL) is ca.DocState.AUTHORED


def test_ready_document_is_left_alone(tmp_path) -> None:
    _write(tmp_path, ca.LIMITS_REL, _AUTHORED.replace("limits_ready: no", "limits_ready: yes"))
    assert ca.classify_document(tmp_path, ca.LIMITS_REL) is ca.DocState.READY


def test_plan_maps_state_to_action(tmp_path) -> None:
    _write(tmp_path, ca.LIMITS_REL, _AUTHORED)  # authored -> review
    # overview absent -> draft
    plan = ca.build_authoring_plan(tmp_path)
    actions = {doc.rel: doc.action for doc in plan.documents}
    assert actions[ca.LIMITS_REL] == "review"
    assert actions[ca.OVERVIEW_REL] == "draft"


# ── the project description ───────────────────────────────────────────────────

def test_description_is_found_in_preference_order(tmp_path) -> None:
    _write(tmp_path, "DESCRIPTION.md", "what this is\n")
    assert ca.find_description(tmp_path) == "DESCRIPTION.md"
    _write(tmp_path, "README.md", "what this is\n")
    assert ca.find_description(tmp_path) == "README.md"


def test_empty_readme_does_not_count_as_a_description(tmp_path) -> None:
    _write(tmp_path, "README.md", "   \n\n")
    assert ca.find_description(tmp_path) is None


def test_advice_is_raised_only_when_there_is_work_to_do(tmp_path) -> None:
    ready = _AUTHORED.replace("limits_ready: no", "limits_ready: yes")
    _write(tmp_path, ca.LIMITS_REL, ready)
    _write(tmp_path, ca.OVERVIEW_REL, "# O\n\n- project_context_ready: yes\n")
    assert not ca.build_authoring_plan(tmp_path).needs_description_advice

    _write(tmp_path, ca.OVERVIEW_REL, "# O\n\n- project_context_ready: no\n")
    assert ca.build_authoring_plan(tmp_path).needs_description_advice


# ── confirmation is the only thing that moves a flag ──────────────────────────

def test_confirming_a_draft_writes_it_and_marks_ready(tmp_path) -> None:
    content = "# Agent Operational Limits\n\n## Metadata\n\n- limits_ready: no\n\nbody\n"

    ca.confirm_document(tmp_path, ca.LIMITS_REL, content=content)

    written = (tmp_path / ca.LIMITS_REL).read_text()
    assert ca.flag_is_yes(written, "limits_ready")
    assert "body" in written


def test_confirming_a_review_does_not_touch_the_operators_prose(tmp_path) -> None:
    _write(tmp_path, ca.LIMITS_REL, _AUTHORED)

    ca.confirm_document(tmp_path, ca.LIMITS_REL)

    written = (tmp_path / ca.LIMITS_REL).read_text()
    assert ca.flag_is_yes(written, "limits_ready")
    # Everything except the flag line is byte-identical.
    assert written.replace("limits_ready: yes", "limits_ready: no") == _AUTHORED


def test_confirming_a_document_without_a_flag_adds_the_metadata_block(tmp_path) -> None:
    _write(tmp_path, ca.LIMITS_REL, "# Agent Operational Limits\n\nsome prose\n")

    ca.confirm_document(tmp_path, ca.LIMITS_REL)

    written = (tmp_path / ca.LIMITS_REL).read_text()
    assert ca.flag_is_yes(written, "limits_ready")
    assert "some prose" in written


def test_confirming_a_missing_document_without_content_fails(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        ca.confirm_document(tmp_path, ca.LIMITS_REL)


# ── drafting and review never call out on their own ───────────────────────────

class _Provider:
    name, model, mode, credential_ref = "test", "m", "env", "K"
    base_url = "https://example.invalid/v1"


def test_draft_leaves_the_flag_at_no(tmp_path, monkeypatch) -> None:
    _write(tmp_path, "README.md", "a service that ingests invoices\n")
    monkeypatch.setattr(
        ca, "_parse_json_object", lambda raw: json.loads(raw)
    )
    monkeypatch.setattr(
        "governancekit.agent_scope.request_completion",
        lambda *a, **k: json.dumps(
            {"overview": "the product", "limits": "the boundaries", "unknowns": ["deploy target"]}
        ),
    )
    plan = ca.build_authoring_plan(tmp_path)

    proposals = ca.draft_documents(tmp_path, plan, _Provider())

    assert {p.rel for p in proposals} == {ca.OVERVIEW_REL, ca.LIMITS_REL}
    for proposal in proposals:
        # A proposal is never ready: only the operator's confirmation moves the flag.
        marker = "limits_ready" if proposal.rel == ca.LIMITS_REL else "project_context_ready"
        assert not ca.flag_is_yes(proposal.content, marker)
        assert "deploy target" in proposal.content
    assert not (tmp_path / ca.LIMITS_REL).exists()  # nothing was written


def test_review_reports_findings_and_writes_nothing(tmp_path, monkeypatch) -> None:
    _write(tmp_path, ca.LIMITS_REL, _AUTHORED)
    before = (tmp_path / ca.LIMITS_REL).read_text()
    monkeypatch.setattr(
        "governancekit.agent_scope.request_completion",
        lambda *a, **k: json.dumps(
            {"findings": [{"section": "Not allowed", "detail": "no rule about PII exports"}]}
        ),
    )
    plan = ca.build_authoring_plan(tmp_path)

    proposals = ca.review_documents(tmp_path, plan, _Provider())

    assert [p.rel for p in proposals] == [ca.LIMITS_REL]
    assert proposals[0].action == "review"
    assert proposals[0].content is None
    assert proposals[0].findings[0].detail == "no rule about PII exports"
    assert (tmp_path / ca.LIMITS_REL).read_text() == before


def test_a_non_json_answer_is_refused(tmp_path, monkeypatch) -> None:
    _write(tmp_path, "README.md", "x\n")
    monkeypatch.setattr(
        "governancekit.agent_scope.request_completion", lambda *a, **k: "I think that..."
    )
    plan = ca.build_authoring_plan(tmp_path)

    with pytest.raises(RuntimeError, match="not valid JSON"):
        ca.draft_documents(tmp_path, plan, _Provider())


def test_installer_seeded_docs_readme_is_not_a_description(tmp_path) -> None:
    # The installer writes docs/README.md as a folder marker. Accepting it as the
    # project's description would suppress the advice exactly where it is needed.
    _write(tmp_path, "docs/README.md", "# Project Documentation\n\nThis folder is yours.\n")
    assert ca.find_description(tmp_path) is None
