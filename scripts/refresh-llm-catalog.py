#!/usr/bin/env python3
"""Re-derive `governancekit/_llm_catalog.json` from its source catalog.

The kit offers an operator a list of free models. A list typed by hand is a second
place to be wrong; a list copied once and never checked is the same thing with a
delay. So the file records where it came from and when, and this script can prove
that it still agrees with its source.

    python3 scripts/refresh-llm-catalog.py                 # refresh from the source
    python3 scripts/refresh-llm-catalog.py --check         # verify, write nothing
    python3 scripts/refresh-llm-catalog.py --source PATH   # override the source

`--check` exits non-zero when the stored catalog disagrees with the source, so a
release runner can prove the offer the kit makes is still true.

The source is littlelm-proxy's `catalog/free-models.json`, which is itself derived
from the OpenRouter models API (recorded in its `sources`). This script deliberately
does NOT hit the network: the sibling project owns that step and its own refresh
cadence. Coupling the two runtimes is a separate decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def _default_source() -> Path:
    """Where the source catalog lives, searched rather than assumed.

    An absolute path under one operator's home is a source that exists on exactly one
    machine: `--check` there would exit 2 everywhere else, so "a release runner can
    prove the offer is still true" would be a claim about this laptop. Searched
    relative to this repository first, then the recorded `derived_from`.
    """
    here = Path(__file__).resolve().parent.parent
    candidates = [
        here.parent / "littlelm-proxy" / "catalog" / "free-models.json",
        here.parent.parent / "littlelm-proxy" / "catalog" / "free-models.json",
    ]
    try:
        recorded = json.loads((here / "governancekit" / "_llm_catalog.json").read_text())
        if recorded.get("derived_from"):
            candidates.append(Path(recorded["derived_from"]))
    except (OSError, json.JSONDecodeError):
        pass
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]
TARGET = Path(__file__).resolve().parent.parent / "governancekit" / "_llm_catalog.json"

_COMMENT = (
    "Free, OpenAI-compatible models the kit may offer an operator. Derived from "
    "littlelm-proxy's catalog by scripts/refresh-llm-catalog.py — do not hand-edit: "
    "what makes this file trustworthy is that it was read off a source, not typed. "
    "Only models advertising `tools` are kept; the authoring flow needs them."
)


def build(source: Path) -> dict:
    """Project the source catalog onto what this kit is allowed to offer.

    Three filters, each with a reason:

    * no ``tools`` support — the authoring flow asks for structured output, so a model
      that cannot take tools cannot do the job the offer implies;
    * duplicate ids and a null ``context_length`` — snapshot noise, and a context
      length is the one number an operator compares;
    * everything else is kept verbatim, including ``policy`` and ``access``, because
      the operator-facing sentence "free does not mean keyless" belongs to the source.
    """
    raw = json.loads(source.read_text(encoding="utf-8"))
    seen: set[str] = set()
    models = []
    for model in sorted(raw["models"], key=lambda m: (-(m.get("context_length") or 0), m["id"])):
        if model["id"] in seen or not model.get("context_length"):
            continue
        if "tools" not in model.get("supported_parameters", []):
            continue
        seen.add(model["id"])
        models.append({
            "id": model["id"],
            "name": model["name"],
            "provider": model["provider"],
            "api_base": model["api_base"],
            "context_length": model["context_length"],
            "status": model.get("status", ""),
        })
    return {
        "_comment": _COMMENT,
        "schema_version": 1,
        "generated_at": raw["generated_at"],
        "derived_from": str(source),
        "sources": raw["sources"],
        "policy": raw["policy"],
        "access": raw["access"],
        "provider_candidates": raw["provider_candidates"],
        "models": models,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only; write nothing")
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    if args.source is None:
        args.source = _default_source()

    if not args.source.is_file():
        print(
            f"ERROR: source catalog not found at {args.source}.\n"
            "  The stored catalog keeps working — it carries its own `generated_at` —\n"
            "  but nothing can prove it is current until the source is reachable.",
            file=sys.stderr,
        )
        return 2

    fresh = build(args.source)
    rendered = json.dumps(fresh, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not TARGET.is_file():
            print(f"ERROR: {TARGET} is missing", file=sys.stderr)
            return 1
        if TARGET.read_text(encoding="utf-8") != rendered:
            print(
                "ERROR: the stored LLM catalog disagrees with its source.\n"
                f"  stored:  {TARGET}\n"
                f"  source:  {args.source} (generated_at {fresh['generated_at']})\n"
                "  Run this script without --check to refresh it.",
                file=sys.stderr,
            )
            return 1
        print(f"LLM catalog is current with {args.source} ({fresh['generated_at']})")
        return 0

    TARGET.write_text(rendered, encoding="utf-8")
    print(f"LLM catalog refreshed from {args.source}")
    print(f"  generated_at: {fresh['generated_at']}")
    print(f"  models kept:  {len(fresh['models'])} of {len(json.loads(args.source.read_text())['models'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
