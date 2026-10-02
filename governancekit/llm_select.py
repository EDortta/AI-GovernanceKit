"""Select a tested well-known LLM provider for a project."""

from __future__ import annotations

from pathlib import Path

from .llm_test import _credential_candidate, _probe
from .project_config import ProviderConfig, apply_project_config_plan, build_project_config_plan
from .scope_conversation import _LLM_PRESETS


def select_well_known_provider(
    root: Path,
    name: str,
    credentials_dir: Path,
    *,
    development: bool = False,
) -> tuple[ProviderConfig, list[str]]:
    root = root.resolve()
    key = name.strip().lower()
    if key not in _LLM_PRESETS:
        raise RuntimeError(
            f"unknown well-known provider {name!r}; expected one of: "
            + ", ".join(sorted(_LLM_PRESETS))
        )

    credentials_dir = credentials_dir.expanduser().resolve()
    credential = _credential_candidate(credentials_dir, key)
    if credential is None:
        raise RuntimeError(f"credential for {key} not found in {credentials_dir}")

    base_url, model, _env_name = _LLM_PRESETS[key]

    # Probe through a temporary project-shaped symlink first. Nothing is persisted
    # unless the provider actually works.
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        probe_root = Path(temp)
        link_dir = probe_root / ".credentials" / "llm"
        link_dir.mkdir(parents=True)
        probe_link = link_dir / f"{key}.key"
        probe_link.symlink_to(credential)
        candidate = ProviderConfig(
            name=key,
            purpose="governance-adoption",
            base_url=base_url,
            model=model,
            mode="file-ref",
            credential_ref=f".credentials/llm/{key}.key",
            validation="tested-external-reference",
            role="primary",
        )
        result = _probe(candidate, probe_root, allow_symlink=True)
        if not result.ok:
            raise RuntimeError(
                f"provider {key}/{model} failed validation before selection: {result.detail}"
            )

    local_dir = root / ".credentials" / "llm"
    local_dir.mkdir(parents=True, exist_ok=True)
    local_dir.chmod(0o700)
    local_link = local_dir / f"{key}.key"
    if local_link.exists() or local_link.is_symlink():
        if local_link.is_symlink() and local_link.resolve() == credential:
            pass
        else:
            raise RuntimeError(
                f"{local_link.relative_to(root)} already exists and does not point to the selected credential"
            )
    else:
        local_link.symlink_to(credential)

    selected = ProviderConfig(
        name=key,
        purpose="governance-adoption",
        base_url=base_url,
        model=model,
        mode="file-ref",
        credential_ref=local_link.relative_to(root).as_posix(),
        validation="tested-external-reference",
        role="primary",
    )
    plan = build_project_config_plan(
        root,
        provider_configs=[selected],
        development=development,
    )
    written = apply_project_config_plan(plan)
    return selected, written
