"""Deterministic context selection, budgeting, provenance, and inspection."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol, Sequence

import yaml
from jsonschema import Draft202012Validator


class ContextError(RuntimeError):
    """A context contract or hard budget limit was violated."""


class TokenCounter(Protocol):
    estimated: bool
    name: str
    tokenizer: str | None
    precise_for: str | None

    def count(self, text: str) -> int:
        """Return the token count for text."""


class DeterministicTokenCounter:
    """Provider-neutral fallback: one token per four Unicode characters."""

    estimated = True
    name = "deterministic_chars_div_4"
    tokenizer = None
    precise_for = None

    def count(self, text: str) -> int:
        return math.ceil(len(text) / 4)


class TiktokenCounter:
    """Tokenizer-specific estimate, activated only when tiktoken is installed."""

    estimated = True
    name = "tiktoken_cl100k_base"
    tokenizer = "cl100k_base"
    precise_for = None

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
    usable_budget: int
    category_tokens: dict[str, int]
    category_budgets: dict[str, int]
    sources: list[Source]
    warnings: list[str]
    duplicates: list[dict[str, Any]]
    exact_count: bool
    counter: str
    count_mode: str
    tokenizer: str | None
    target_model: str | None
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
            "usable_budget": self.usable_budget,
            "category_tokens": self.category_tokens,
            "category_budgets": self.category_budgets,
            "sources": [source.metadata() for source in self.sources],
            "warnings": self.warnings,
            "duplicates": self.duplicates,
            "exact_count": self.exact_count,
            "counter": self.counter,
            "count_mode": self.count_mode,
            "tokenizer": self.tokenizer,
            "target_model": self.target_model,
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
    terms: dict[str, int],
    max_sections: int,
    max_section_tokens: int,
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
    needles = dict(terms)
    for term in entry.get("terms", []):
        if len(term) >= 3:
            needles[term.casefold()] = max(needles.get(term.casefold(), 0), 3)
    ranked: list[tuple[int, int, str, str]] = []
    for index, (heading, _, _, body) in enumerate(sections):
        haystack = f"{heading}\n{body}".casefold()
        score = sum(haystack.count(needle) * weight for needle, weight in needles.items())
        if score:
            ranked.append((-score, index, heading, body))
    ranked.sort()
    chunks: list[str] = []
    provenance: list[str] = []
    for _, _, heading, body in ranked[:max_sections]:
        if counter.count(body) > max_section_tokens:
            raise ContextError(
                f"retrieved section '{heading}' exceeds max_section_tokens={max_section_tokens}; "
                "declare a narrower section instead of silently truncating it"
            )
        chunks.append(body)
        provenance.append(f"retrieve:{heading}")
    return "\n\n".join(chunks), tuple(provenance)


_STOPWORDS = {"deve", "arquivo", "contexto", "projeto", "testes", "implementar", "para", "como", "with", "from", "that", "this"}


def _terms(task: str, issue_path: Path | None) -> dict[str, int]:
    values: dict[str, int] = {task.casefold(): 5}
    if issue_path and issue_path.is_file():
        text = issue_path.read_text(encoding="utf-8")
        for exact in re.findall(r"`([^`]+)`|(?:[\w.-]+/)+[\w.-]+", text):
            if exact:
                values[exact.casefold()] = 10
        for heading in re.findall(r"(?m)^#{1,6}\s+(.+)$", text):
            for word in re.findall(r"[A-Za-zÀ-ÿ_][\wÀ-ÿ.-]{3,}", heading):
                values[word.casefold()] = max(values.get(word.casefold(), 0), 5)
        for word in re.findall(r"[A-Za-zÀ-ÿ_][\wÀ-ÿ.-]{3,}", text):
            folded = word.casefold()
            if folded not in _STOPWORDS:
                values.setdefault(folded, 1)
    return values


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
            containment = len(left_blocks & right_blocks) / min(
                len(left_blocks), len(right_blocks)
            )
            if 0.5 <= score < 1:
                findings.append(
                    {
                        "kind": "substantial_overlap",
                        "paths": [left.path, right.path],
                        "score": round(score, 3),
                    }
                )
            elif containment >= 0.7:
                findings.append(
                    {
                        "kind": "contained_overlap",
                        "paths": [left.path, right.path],
                        "score": round(containment, 3),
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
    strict: bool = True,
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
    entries.extend(_entry(value, "task_contracts") for value in tasks[task].get("include", []))
    for risk in risks:
        entries.extend(_entry(value, "risk_contracts") for value in manifest["risks"][risk].get("include", []))
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

    budget = int(manifest["budgets"]["total_input_tokens"])
    category_budgets = {
        str(name): int(value) for name, value in manifest["budgets"]["categories"].items()
    }
    reserve = category_budgets["reserve"]
    usable_budget = budget - reserve
    if usable_budget <= 0:
        raise ContextError("reserve must be smaller than total_input_tokens")
    retrieval = manifest["retrieval"]
    excluded = manifest.get("exclude_by_default", [])
    issue_abs = (issue if issue and issue.is_absolute() else root / issue).resolve() if issue else None
    terms = _terms(task, issue_abs)
    candidates: list[Source] = []
    selected: list[Source] = []
    warnings: list[str] = []
    hard_violations: list[str] = []
    seen_paths: set[Path] = set()
    category_tokens = {name: 0 for name in category_budgets}

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
            int(retrieval["max_sections"]),
            int(retrieval["max_section_tokens"]),
            counter,
        )
        if not content:
            if required:
                raise ContextError(f"required retrieval produced no content: {rel}")
            warnings.append(f"no matching content retrieved: {rel}")
            continue
        tokens = counter.count(content)
        category = str(entry["category"])
        if category not in category_budgets or category == "reserve":
            raise ContextError(f"source {rel} references unbudgeted category: {category}")
        candidates.append(
            Source(rel, category, tokens, required, str(entry["mode"]), content, provenance)
        )
        seen_paths.add(path)

    required_total = sum(source.tokens for source in candidates if source.required)
    required_categories = {name: 0 for name in category_budgets}
    for source in candidates:
        if source.required:
            required_categories[source.category] += source.tokens
    if required_total > usable_budget:
        hard_violations.append(
            f"required context exceeds usable budget: {required_total}/{usable_budget} "
            f"(reserve {reserve})"
        )
    for category, used in required_categories.items():
        if used > category_budgets[category]:
            hard_violations.append(
                f"required category exceeds budget: {category} {used}/{category_budgets[category]}"
            )
    if hard_violations and strict:
        raise ContextError("; ".join(hard_violations))

    total = 0
    for source in candidates:
        violation = (
            total + source.tokens > usable_budget
            or category_tokens[source.category] + source.tokens
            > category_budgets[source.category]
        )
        if violation and not source.required:
            warnings.append(
                f"optional source omitted by budget: {source.path} ({source.tokens} tokens)"
            )
            continue
        selected.append(source)
        category_tokens[source.category] += source.tokens
        total += source.tokens

    result = ContextResult(
        task=task,
        risks=list(risks),
        total_tokens=total,
        budget=budget,
        usable_budget=usable_budget,
        category_tokens=category_tokens,
        category_budgets=category_budgets,
        sources=selected,
        warnings=warnings,
        duplicates=_duplicates(selected),
        exact_count=not getattr(counter, "estimated", True),
        counter=counter.name,
        count_mode="estimate" if getattr(counter, "estimated", True) else "exact",
        tokenizer=getattr(counter, "tokenizer", None),
        target_model=getattr(counter, "precise_for", None),
        exceeded=bool(hard_violations) or total > usable_budget or any(
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
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_version": manifest["version"],
        "repository": root.name,
        "git_commit": _git_commit(root),
        "work_id": _work_id(issue),
        "phase": "context_build",
        "task": result.task,
        "total_tokens": result.total_tokens,
        "budget": result.budget,
        "usable_budget": result.usable_budget,
        "sources": result.category_tokens,
        "source_paths": [source.path for source in result.sources],
        "count_mode": result.count_mode,
        "counter": result.counter,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def _git_commit(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def prune_telemetry(
    root: Path, manifest_path: Path | None = None, now: datetime | None = None
) -> int:
    manifest = load_manifest(root.resolve(), manifest_path)
    path = root.resolve() / manifest["telemetry"]["path"]
    if not path.is_file():
        return 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        days=int(manifest["telemetry"]["retention_days"])
    )
    kept: list[str] = []
    removed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
            timestamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            kept.append(line)
            continue
        if timestamp < cutoff:
            removed += 1
        else:
            kept.append(line)
    path.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
    return removed


def format_context(result: ContextResult) -> str:
    qualifier = result.count_mode
    lines = [
        f"Context budget: {result.total_tokens:,} / {result.usable_budget:,} usable "
        f"tokens ({result.budget:,} total, {result.category_budgets['reserve']:,} reserve; "
        f"{qualifier})",
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
