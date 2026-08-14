from __future__ import annotations

import unittest
from pathlib import Path

from governancekit import install_agents as ia

_AGENTS = Path(__file__).resolve().parents[2] / "Agents"

# A synthetic answer for every declared slot. Uppercase and brace-free, so it passes
# `_render_table` and can only manufacture a token by combining with the FILE's own
# braces — which is the whole question this gate asks.
_PROBE = {token: "PROBEVALUE" for token in ia._PLACEHOLDER_DESCRIPTIONS}
_PROBE.update({token: "PROBEVALUE" for token in ia._RETIRED_PLACEHOLDERS})
# One value that is itself a declared token name: with doubled braces around the slot
# this composes into a live token, which is the sharp case no rule about values can
# ever catch, because the braces belong to the file.
_PROBE["ORG_NAME"] = "PROJECT_SLUG"


class ShippedTextCannotComposeTest(unittest.TestCase):
    """The layer that keeps a composable template out of a release.

    `_render_table` refuses a value carrying a brace and `_render_file_text` drops a
    token that composes, but both are runtime: they cost the operator a raw slot and
    a warning about a file they may not own. This gate is the one that stops it
    shipping, and it runs against the tree `_prerender_source` renders — the
    AI-Agents checkout, which is what `_download` unpacks.

    It asks the REAL question by running the real function. An earlier cut enumerated
    three brace shapes with a regex, and a council lens broke it in one try:
    `{{{{ORG_NAME}}_PAYLOAD}}` composes `{{PROJECT_SLUG}}` and matched none of the
    three. A gate written from a list of known shapes only ever knows the shapes
    someone thought of; the property is `_render_file_text`, so the property is what
    runs here.
    """

    def test_the_corpus_this_gate_needs_is_present(self) -> None:
        # Deliberately a FAILURE and not a skip. A skipped security layer is
        # indistinguishable from a green one, and this file resolves its corpus by
        # filesystem adjacency — the normal condition on a fresh clone is absent.
        self.assertTrue(
            _AGENTS.is_dir(),
            f"the AI-Agents checkout is not at {_AGENTS}. This gate reads the tree "
            "the installer renders; without it the render layer ships unverified.",
        )

    def test_no_shipped_file_composes_a_token_when_rendered(self) -> None:
        if not _AGENTS.is_dir():
            self.fail("see test_the_corpus_this_gate_needs_is_present")

        offenders: dict[str, list[str]] = {}
        for path in sorted(_AGENTS.rglob("*")):
            if ".git" in path.parts or path.is_symlink() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            _, _, blocked = ia._render_file_text(text, _PROBE)
            if blocked:
                offenders[str(path.relative_to(_AGENTS))] = sorted(blocked)

        self.assertEqual(
            offenders, {},
            "these shipped files make the render manufacture placeholder syntax; the "
            "operator cannot fix this with any value they set",
        )

    def test_the_gate_catches_a_shape_no_regex_list_would_have(self) -> None:
        # Built at runtime: writing the payload into a file is how a defect gets
        # shipped by the prose that documents it. This is the shape that defeated the
        # regex version — the token name is SPLIT across the file's braces and the
        # value, so no enumeration of brace patterns contains it.
        composable = "{{" + "{{ORG_NAME}}" + "_PAYLOAD}}"
        _, count, blocked = ia._render_file_text(composable, _PROBE)

        self.assertEqual(blocked, {"ORG_NAME"})
        self.assertEqual(count, 0)

    def test_the_gate_does_not_fire_on_ordinary_kit_text(self) -> None:
        rendered, count, blocked = ia._render_file_text(
            "owner: {{ORG_NAME}}\nslug: {{PROJECT_SLUG}}\n", _PROBE
        )

        self.assertEqual(blocked, set())
        self.assertEqual(count, 2)
        self.assertNotIn("{{", rendered)


if __name__ == "__main__":
    unittest.main()
