"""The offer the kit makes to an operator is data with an origin, not three literals.

`_llm_presets()` used to be a hand-written dict pinning three model names for which no
document in either repository gave a reason — the council of 2026-08-12 reported it as
"os modelos pinados não têm justificativa escrita em lugar nenhum". The catalog answers
that: every entry now carries where it came from and when.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from governancekit import llm_catalog
from governancekit.scope_conversation import _llm_presets

ROOT = Path(__file__).resolve().parent.parent


class CatalogTest(unittest.TestCase):
    def test_every_preset_comes_from_the_catalog(self) -> None:
        # Mutation: write a preset by hand in scope_conversation → red.
        self.assertEqual(_llm_presets(), llm_catalog.presets())
        self.assertTrue(_llm_presets(), "the interview needs defaults to offer")

    def test_the_catalog_only_offers_models_that_can_do_the_work(self) -> None:
        # The authoring flow asks for structured output. A model without `tools`
        # cannot do the job the offer implies, and offering it is a promise the kit
        # cannot keep. The source catalog carries four such entries.
        source = json.loads(
            (ROOT / "governancekit" / "_llm_catalog.json").read_text(encoding="utf-8")
        )
        ids = [m["id"] for m in source["models"]]
        self.assertEqual(len(ids), len(set(ids)), "the source snapshot has duplicate ids")
        for model in llm_catalog.free_models():
            self.assertGreater(model.context_length, 0)
            self.assertNotIn("lyria", model.id, "audio models are not writers")
            self.assertNotIn("content-safety", model.id)

    def test_the_catalog_records_where_it_came_from_and_when(self) -> None:
        # A snapshot without provenance is a second place to be wrong with no way to
        # find out. `scripts/refresh-llm-catalog.py --check` is what makes it checkable.
        source = json.loads(
            (ROOT / "governancekit" / "_llm_catalog.json").read_text(encoding="utf-8")
        )
        for key in ("generated_at", "derived_from", "sources", "policy"):
            self.assertTrue(str(source.get(key, "")).strip(), f"catalog lost its {key}")
        self.assertIn("free-models.json", source["derived_from"])

    def test_the_offer_carries_the_policy_that_free_is_not_keyless(self) -> None:
        # The one sentence an operator has to read before picking a free model, and
        # the reason the kit never obtains a key on their behalf.
        self.assertIn("keyless", llm_catalog.policy().lower())
        for offer in llm_catalog.provider_offers():
            self.assertTrue(offer.signup_url.startswith("https://"), offer.name)

    def test_the_widest_free_option_is_offered_first(self) -> None:
        offers = llm_catalog.provider_offers()
        self.assertEqual(offers[0].name, "openrouter")
        self.assertGreater(offers[0].free_models, 1)


if __name__ == "__main__":
    unittest.main()
