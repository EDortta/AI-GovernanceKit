"""Deterministic context selection, budgeting, provenance, and inspection."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

import yaml
from jsonschema import Draft202012Validator


class ContextError(RuntimeError):
    """A context contract or hard budget limit was violated."""


class TokenCounter(Protocol):
    exact: bool
    name: str

    def count(self, text: str) -> int:
        """Return the token count for text."""


class DeterministicTokenCounter:
    """Provider-neutral fallback: one token per four Unicode characters."""

    exact = False
    name = "deterministic_chars_div_4"

    def count(self, text: str) -> int:
        return math.ceil(len(text) / 4)


class TiktokenCounter:
    """Optional exact counter, activated only when tiktoken is installed."""

    exact = True
    name = "tiktoken_cl100k_base"

    def __init__(self) -> None:
        import tiktoken

        self._encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text))


def default_token_counter() -> TokenCounter:
    try:
        return TiktokenCounter()
    except (ImportError, ModuleNotFoundError):
        return DeterministicTokenCounter()


@dataclass(frozen=True)
class Source:
    path: str
    category: str
    tokens: int
    required: bool
    mode: str
    content: str
    provenance: tuple[str, ...]

    def metadata(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category,
            "tokens": self.tokens,
            "required": self.required,
            "mode": self.mode,
            "provenance": list(self.provenance),
        }


@dataclass
class ContextResult:
    task: str
    risks: list[str]
    total_tokens: int
    budget: int
    category_tokens: dict[str, int]
    category_budgets: dict[str, int]
    sources: list[Source]
    warnings: list[str]
    duplicates: list[dict[str, Any]]
    exact_count: bool
    counter: str
    exceeded: bool = False
    hard_violations: list[str] = field(default_factory=list)

    @property
    def content(self) -> str:
        blocks = []
        for source in self.sources:
            provenance = ", ".join(source.provenance)
            blocks.append(f"<!-- source: {source.path}; {provenance} -->\n{source.content}")
        return "\n\n".join(blocks)

    def as_dict(self, include_content: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "task": self.task,
            "risks": self.risks,
            "total_tokens": self.total_tokens,
            "budget": self.budget,
            "category_tokens": self.category_tokens,
            "category_budgets": self.category_budgets,
            "sources": [source.metadata() for source in self.sources],
            "warnings": self.warnings,
            "duplicates": self.duplicates,
            "exact_count": self.exact_count,
            "counter": self.counter,
            "exceeded": self.exceeded,
            "hard_violations": self.hard_violations,
        }
        if include_content:
            result["content"] = self.content
        return result


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContextError(f"cannot load manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContextError(f"manifest must be an object: {path}")
    return value


def load_manifest(root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    path = manifest_path or root / ".docs/context-manifest.yaml"
    if not path.is_absolute():
        path = root / path
    manifest = _load_yaml(path)
    schema_ref = manifest.get("$schema")
    if not isinstance(schema_ref, str):
        raise ContextError("manifest requires a $schema path")
    schema_path = (path.parent / schema_ref).resolve()
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextError(f"cannot load manifest schema {schema_path}: {exc}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors
        )
        raise ContextError(f"invalid context manifest: {details}")
    return manifest


def _entry(value: str | dict[str, Any], category: str, required: bool = False) -> dict[str, Any]:
    if isinstance(value, str):
        return {"path": value, "category": category, "required": required, "mode": "full"}
    result = dict(value)
    result.setdefault("category", category)
    result.setdefault("required", required)
    result.setdefault("mode", "full")
    return result


def _excluded(path: str, patterns: Sequence[str]) -> bool:
    candidate = Path(path)
    return any(candidate.match(pattern) for pattern in patterns)


def _markdown_sections(text: str) -> list[tuple[str, int, int, str]]:
    matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))
    sections: list[tuple[str, int, int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(2).strip(), match.start(), end, text[match.start():end].strip()))
    return sections


def _select_content(
    text: str,
    mode: str,
    entry: dict[str, Any],
    terms: Sequence[str],
    max_chunks: int,
    max_chunk_tokens: int,
    counter: TokenCounter,
) -> tuple[str, tuple[str, ...]]:
    if mode == "full":
        return text, ("full",)
    sections = _markdown_sections(text)
    if mode == "sections":
        wanted = {str(item).casefold() for item in entry.get("sections", [])}
        selected = [(heading, body) for heading, _, _, body in sections if heading.casefold() in wanted]
        missing = wanted - {heading.casefold() for heading, _ in selected}
        if missing:
            raise ContextError(f"missing declared section(s): {', '.join(sorted(missing))}")
        return "\n\n".join(body for _, body in selected), tuple(
            f"section:{heading}" for heading, _ in selected
        )
    if mode != "retrieve":
        raise ContextError(f"unsupported document mode: {mode}")
    needles = {term.casefold() for term in [*terms, *entry.get("terms", [])] if len(term) >= 3}
    ranked: list[tuple[int, int, str, str]] = []
    for index, (heading, _, _, body) in enumerate(sections):
        haystack = f"{heading}\n{body}".casefold()
        score = sum(haystack.count(needle) for needle in needles)
        if score:
            ranked.append((-score, index, heading, body))
    ranked.sort()
    chunks: list[str] = []
    provenance: list[str] = []
    for _, _, heading, body in ranked[:max_chunks]:
        if counter.count(body) > max_chunk_tokens:
            raise ContextError(
                f"retrieved section '{heading}' exceeds max_chunk_tokens={max_chunk_tokens}; "
                "declare a narrower section instead of silently truncating it"
            )
        chunks.append(body)
        provenance.append(f"retrieve:{heading}")
    return "\n\n".join(chunks), tuple(provenance)


def _terms(task: str, issue_path: Path | None) -> list[str]:
    values = [task, *re.findall(r"[A-Za-zÀ-ÿ_][\wÀ-ÿ.-]{2,}", task)]
    if issue_path and issue_path.is_file():
        text = issue_path.read_text(encoding="utf-8")
        values.extend(re.findall(r"[A-Za-zÀ-ÿ_][\wÀ-ÿ.-]{3,}", text))
    return sorted(set(values), key=str.casefold)


def _normalized_blocks(text: str) -> set[str]:
    blocks = re.split(r"\n\s*\n", text.casefold())
    return {
        re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", block)).strip()
        for block in blocks
        if len(re.sub(r"\s+", " ", block).strip()) >= 80
    }


def _duplicates(sources: Sequence[Source]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for source in sources:
        digest = hashlib.sha256(source.content.encode()).hexdigest()
        if digest in hashes:
            findings.append(
                {"kind": "identical_content", "paths": [hashes[digest], source.path], "score": 1.0}
            )
        else:
            hashes[digest] = source.path
    for left_index, left in enumerate(sources):
        left_blocks = _normalized_blocks(left.content)
        if not left_blocks:
            continue
        for right in sources[left_index + 1:]:
            right_blocks = _normalized_blocks(right.content)
            union = left_blocks | right_blocks
            score = len(left_blocks & right_blocks) / len(union) if union else 0
            if 0.5 <= score < 1:
                findings.append(
                    {
                        "kind": "substantial_overlap",
                        "paths": [left.path, right.path],
                        "score": round(score, 3),
                    }
                )
    return findings


def build_context(
    root: Path,
    task: str,
    risks: Sequence[str] = (),
    issue: Path | None = None,
    manifest_path: Path | None = None,
    counter: TokenCounter | None = None,
    write_telemetry: bool = False,
) -> ContextResult:
    root = root.resolve()
    counter = counter or default_token_counter()
    manifest = load_manifest(root, manifest_path)
    tasks = manifest["tasks"]
    if task not in tasks:
        raise ContextError(f"unknown task '{task}'; expected one of: {', '.join(sorted(tasks))}")
    unknown_risks = sorted(set(risks) - set(manifest.get("risks", {})))
    if unknown_risks:
        raise ContextError(f"unknown risk(s): {', '.join(unknown_risks)}")

    entries: list[dict[str, Any]] = []
    entries.extend(_entry(value, "base_contracts", True) for value in manifest["base"]["required"])
    entries.extend(_entry(value, "project_context") for value in manifest.get("project", {}).get("include", []))
    entries.extend(_entry(value, "project_context") for value in tasks[task].get("include", []))
    for risk in risks:
        entries.extend(_entry(value, "project_context") for value in manifest["risks"][risk].get("include", []))
    if issue:
        issue_abs = (issue if issue.is_absolute() else root / issue).resolve()
        entries.append(
            {
                "path": str(issue_abs.relative_to(root)),
                "category": "active_work",
                "required": True,
                "mode": "full",
            }
        )
        state_path = issue_abs.parent / "context-state.json"
        if state_path.is_file():
            state_schema_path = root / ".docs/schemas/context-state.schema.json"
            if state_schema_path.is_file():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    state_schema = json.loads(state_schema_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ContextError(f"cannot load active context state: {exc}") from exc
                state_errors = sorted(
                    Draft202012Validator(state_schema).iter_errors(state),
                    key=lambda error: list(error.path),
                )
                if state_errors:
                    details = "; ".join(error.message for error in state_errors)
                    raise ContextError(f"invalid active context state: {details}")
            entries.append(
                {
                    "path": str(state_path.relative_to(root)),
                    "category": "active_work",
                    "required": False,
                    "mode": "full",
                }
            )

    # Mandatory contracts always get first claim on the budget. Otherwise an
    # earlier optional source could make a later mandatory source fail even though
    # omitting the optional source would have produced a valid context.
    entries.sort(key=lambda item: not bool(item.get("required", False)))

    budget = int(manifest["budgets"]["total_input_tokens"])
    category_budgets = {
        str(name): int(value) for name, value in manifest["budgets"]["categories"].items()
    }
    retrieval = manifest["retrieval"]
    excluded = manifest.get("exclude_by_default", [])
    issue_abs = (issue if issue and issue.is_absolute() else root / issue).resolve() if issue else None
    terms = _terms(task, issue_abs)
    selected: list[Source] = []
    warnings: list[str] = []
    hard_violations: list[str] = []
    seen_paths: set[Path] = set()
    category_tokens = {name: 0 for name in category_budgets}
    total = 0

    for entry in entries:
        rel = str(entry["path"])
        required = bool(entry.get("required", False))
        if _excluded(rel, excluded) and not required:
            warnings.append(f"excluded by default: {rel}")
            continue
        path = (root / rel).resolve()
        if path in seen_paths:
            warnings.append(f"duplicate path omitted: {rel}")
            continue
        if not path.is_relative_to(root):
            raise ContextError(f"context path escapes repository root: {rel}")
        if not path.is_file():
            message = f"context file not found: {rel}"
            if required:
                raise ContextError(message)
            warnings.append(message)
            continue
        text = path.read_text(encoding="utf-8")
        content, provenance = _select_content(
            text,
            str(entry["mode"]),
            entry,
            terms,
            int(retrieval["max_chunks"]),
            int(retrieval["max_chunk_tokens"]),
            counter,
        )
        if not content:
            warnings.append(f"no matching content retrieved: {rel}")
            continue
        tokens = counter.count(content)
        category = str(entry["category"])
        category_limit = category_budgets[category]
        violation = total + tokens > budget or category_tokens[category] + tokens > category_limit
        if violation and required:
            reason = (
                f"required source does not fit budget: {rel} ({tokens} tokens, "
                f"category {category} {category_tokens[category] + tokens}/{category_limit}, "
                f"total {total + tokens}/{budget})"
            )
            hard_violations.append(reason)
            raise ContextError(reason)
        if violation:
            warnings.append(f"optional source omitted by budget: {rel} ({tokens} tokens)")
            continue
        selected.append(
            Source(rel, category, tokens, required, str(entry["mode"]), content, provenance)
        )
        seen_paths.add(path)
        category_tokens[category] += tokens
        total += tokens

    result = ContextResult(
        task=task,
        risks=list(risks),
        total_tokens=total,
        budget=budget,
        category_tokens=category_tokens,
        category_budgets=category_budgets,
        sources=selected,
        warnings=warnings,
        duplicates=_duplicates(selected),
        exact_count=counter.exact,
        counter=counter.name,
        exceeded=total > budget or any(
            category_tokens[name] > limit for name, limit in category_budgets.items()
        ),
        hard_violations=hard_violations,
    )
    if write_telemetry:
        _write_telemetry(root, manifest, result, issue_abs)
    return result


def _work_id(issue: Path | None) -> str:
    if issue and issue.is_file():
        match = re.search(r"WK-\d{8}-[\w-]+", issue.read_text(encoding="utf-8"))
        if match:
            return match.group(0)
        state = issue.parent / "context-state.json"
        if state.is_file():
            value = json.loads(state.read_text(encoding="utf-8")).get("work_id")
            if isinstance(value, str) and value:
                return value
    raise ContextError("telemetry requires a work_id in the issue or context-state.json")


def _write_telemetry(
    root: Path, manifest: dict[str, Any], result: ContextResult, issue: Path | None
) -> None:
    path = root / manifest["telemetry"]["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "work_id": _work_id(issue),
        "phase": "context_build",
        "task": result.task,
        "total_tokens": result.total_tokens,
        "budget": result.budget,
        "sources": result.category_tokens,
        "source_paths": [source.path for source in result.sources],
        "exact_count": result.exact_count,
        "counter": result.counter,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def format_context(result: ContextResult) -> str:
    qualifier = "exact" if result.exact_count else "estimated"
    lines = [
        f"Context budget: {result.total_tokens:,} / {result.budget:,} tokens ({qualifier})",
        "",
        "Categories:",
    ]
    for name, limit in result.category_budgets.items():
        used = result.category_tokens.get(name, 0)
        marker = " EXCEEDED" if used > limit else ""
        lines.append(f"- {name}: {used:,} / {limit:,}{marker}")
    lines.extend(["", "Largest contributors:"])
    for index, source in enumerate(sorted(result.sources, key=lambda item: (-item.tokens, item.path)), 1):
        lines.append(f"{index}. {source.path} — {source.tokens:,}")
    if result.duplicates:
        lines.extend(["", "Duplicates:"])
        for finding in result.duplicates:
            lines.append(
                f"- {finding['kind']}: {' = '.join(finding['paths'])} "
                f"(score {finding['score']})"
            )
    if result.warnings:
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in result.warnings]])
    return "\n".join(lines)
