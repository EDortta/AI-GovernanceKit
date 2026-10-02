"""Connectivity tests for configured and well-known LLM providers."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .agent_scope import request_completion
from .project_config import ProviderConfig, load_project_config
from .scope_conversation import _LLM_PRESETS


@dataclass(frozen=True)
class LlmTestResult:
    name: str
    model: str | None
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "model": self.model,
            "ok": self.ok,
            "detail": self.detail,
        }


def _probe(provider: ProviderConfig, root: Path, *, allow_symlink: bool = False) -> LlmTestResult:
    try:
        response = request_completion(
            provider,
            root,
            system="Connectivity test. Reply with exactly OK.",
            user="OK",
            allow_project_credential_symlinks=allow_symlink,
            purpose="provider test",
        )
    except RuntimeError as exc:
        return LlmTestResult(provider.name, provider.model, False, str(exc))
    normalized = " ".join(response.split())
    return LlmTestResult(
        provider.name,
        provider.model,
        True,
        "reachable; completion returned" + (f" ({normalized[:40]})" if normalized else ""),
    )


def check_configured_providers(root: Path) -> list[LlmTestResult]:
    root = root.resolve()
    config = load_project_config(root)
    if config is None:
        return []
    providers = [provider for provider in config.providers if provider.mode != "manual"]
    return [_probe(provider, root) for provider in providers]


def _credential_candidate(directory: Path, name: str) -> Path | None:
    candidates = [
        directory / f"{name}.key",
        directory / name,
        directory / f"{name}.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def check_well_known_from_directory(directory: Path) -> list[LlmTestResult]:
    directory = directory.expanduser().resolve()
    if not directory.is_dir():
        raise RuntimeError(f"credentials directory does not exist: {directory}")

    results: list[LlmTestResult] = []
    for name, (base_url, model, _env_name) in _LLM_PRESETS.items():
        credential = _credential_candidate(directory, name)
        if credential is None:
            results.append(LlmTestResult(name, model, False, "credential file not found"))
            continue
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / ".credentials" / "llm"
            local.mkdir(parents=True)
            link = local / f"{name}.key"
            link.symlink_to(credential)
            provider = ProviderConfig(
                name=name,
                purpose="provider-test",
                base_url=base_url,
                model=model,
                mode="file-ref",
                credential_ref=f".credentials/llm/{name}.key",
                validation="reference-required",
                role="primary",
            )
            results.append(_probe(provider, root, allow_symlink=True))
    return results


def format_llm_test(results: list[LlmTestResult]) -> str:
    lines = ["AI GovernanceKit LLM test"]
    if not results:
        lines.append("  no providers to test")
        return "\n".join(lines)
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(
            f"  {status} {result.name} / {result.model or '(unset)'}: {result.detail}"
        )
    return "\n".join(lines)
