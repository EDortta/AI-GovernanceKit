"""Free, OpenAI-compatible models the kit may offer — as data, with provenance.

The presets used to be three tuples written by hand in `scope_conversation`, pinning
three model names for which no document anywhere gave a reason. A council found that
in the same week it found two other "second place to be wrong" defects, and the
answer here is the answer there: derive the data from a source, record where it came
from and when, and give it a refresh path that can prove it is not stale.

`_llm_catalog.json` is that data. `scripts/refresh-llm-catalog.py --check` proves it
still matches its source. The kit never selects a model on its own and never obtains
a key: the catalog's own policy line says it plainly — *free does not mean keyless*.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_CATALOG_FILE = "_llm_catalog.json"


class CatalogError(RuntimeError):
    """The catalog is missing or unreadable."""


@dataclass(frozen=True)
class FreeModel:
    id: str
    name: str
    provider: str
    api_base: str
    context_length: int


@dataclass(frozen=True)
class ProviderOffer:
    """One way an operator can obtain a key, with the endpoint the kit would use."""

    name: str
    signup_url: str
    api_base: str | None
    model: str | None
    env_var: str | None
    free_models: int
    note: str = ""


# The environment variable each provider's key is conventionally read from. Not in the
# source catalog — it is this kit's own convention, and `scope_conversation` has always
# probed these names.
_ENV_VARS = {
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
}

# Providers the kit knows an endpoint for but that the free catalog does not cover.
# Kept because an operator may already hold a paid key.
_PAID_ENDPOINTS = {
    "openai": ("https://api.openai.com/v1", "gpt-5-mini"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash-lite"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3-super-120b-a12b"),
}


@lru_cache(maxsize=1)
def _catalog() -> dict:
    path = Path(__file__).with_name(_CATALOG_FILE)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogError(f"LLM catalog missing at {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"LLM catalog unreadable at {path}: {exc}") from exc


def generated_at() -> str:
    return str(_catalog().get("generated_at", ""))


def policy() -> str:
    """The one sentence an operator must read before picking a free model."""
    return str(_catalog().get("policy", ""))


def free_models() -> list[FreeModel]:
    return [
        FreeModel(m["id"], m["name"], m["provider"], m["api_base"], int(m["context_length"]))
        for m in _catalog().get("models", [])
    ]


def _best_free(provider: str) -> FreeModel | None:
    """The widest-context free model for a provider — the catalog is sorted by it."""
    for model in free_models():
        if model.provider == provider:
            return model
    return None


def provider_offers() -> list[ProviderOffer]:
    """What the kit can honestly tell an operator they could be using.

    Ordered by what is reachable today: the aggregator that yields the most free
    models for one key first, then the providers whose free tier is account-dependent.
    """
    data = _catalog()
    offers: list[ProviderOffer] = []
    counts: dict[str, int] = {}
    for model in free_models():
        counts[model.provider] = counts.get(model.provider, 0) + 1

    for name, access in data.get("access", {}).items():
        best = _best_free(name)
        offers.append(ProviderOffer(
            name=name,
            signup_url=str(access.get("signup_url", "")),
            api_base=best.api_base if best else None,
            model=best.id if best else None,
            env_var=_ENV_VARS.get(name),
            free_models=counts.get(name, 0),
            note=str(access.get("rate_limit_note", "")),
        ))
    for candidate in data.get("provider_candidates", []):
        name = str(candidate.get("provider", ""))
        if any(offer.name == name for offer in offers):
            continue
        endpoint = _PAID_ENDPOINTS.get(name)
        offers.append(ProviderOffer(
            name=name,
            signup_url=str(candidate.get("signup_url", "")),
            api_base=candidate.get("api_base") or (endpoint[0] if endpoint else None),
            model=endpoint[1] if endpoint else None,
            env_var=_ENV_VARS.get(name),
            free_models=counts.get(name, 0),
            note=str(candidate.get("reason", "")),
        ))
    return offers


def presets() -> dict[str, tuple[str, str, str]]:
    """`name -> (base_url, model, env var)`, derived, for the interview's defaults.

    Replaces a hand-written dict. Every value here now has an origin and a date.
    """
    out: dict[str, tuple[str, str, str]] = {}
    try:
        for offer in provider_offers():
            if offer.api_base and offer.model and offer.env_var:
                out[offer.name] = (offer.api_base, offer.model, offer.env_var)
    except CatalogError:
        # The catalog adds `openrouter` and its free models; it is not what makes the
        # other three work. Losing all four when the file is unreadable turned a
        # traceback into silence — a project holding a gemini key would simply stop
        # being detected, with nothing said. Found in council round 2.
        pass
    for name, (base_url, model) in _PAID_ENDPOINTS.items():
        out.setdefault(name, (base_url, model, _ENV_VARS[name]))
    return out
