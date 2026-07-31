from __future__ import annotations

import argparse
from pathlib import Path

from governancekit.cli import build_parser
from governancekit.install_agents import DEFAULT_REF, KNOWN_TARBALL_SHA256, REPO


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "advanced-usage.html"
GUIDE_PTBR = ROOT / "docs" / "advanced-usage-ptbr.html"
GUIDE_ES = ROOT / "docs" / "advanced-usage-es.html"
LANDING = ROOT / "docs" / "index.html"


def _long_options(parser: argparse.ArgumentParser) -> set[str]:
    found = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for child in action.choices.values():
            found.update(_long_options(child))
    return found


def test_advanced_guide_documents_every_cli_parameter() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    missing = sorted(option for option in _long_options(build_parser()) if option not in guide)
    assert missing == []


def test_landing_links_advanced_guide_and_identity_is_unambiguous() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    landing = LANDING.read_text(encoding="utf-8")

    assert "./advanced-usage.html" in landing
    assert "./advanced-usage-ptbr.html" in landing
    assert "./advanced-usage-es.html" in landing
    assert "data-advanced-link" in landing
    assert "Detalhes avançados de uso" in landing
    assert ".governancekit-identity.json" in guide
    assert "<code>WORKSPACE.md</code> is not required" in guide


def test_advanced_guide_is_available_in_all_landing_languages() -> None:
    guides = {
        GUIDE: ('<html lang="en">', ("./advanced-usage-ptbr.html", "./advanced-usage-es.html")),
        GUIDE_PTBR: ('<html lang="pt-BR">', ("./advanced-usage.html", "./advanced-usage-es.html")),
        GUIDE_ES: ('<html lang="es">', ("./advanced-usage.html", "./advanced-usage-ptbr.html")),
    }
    for path, (language_marker, alternate_guides) in guides.items():
        content = path.read_text(encoding="utf-8")
        assert language_marker in content
        assert "install-agents\n" in content
        assert "install-agents --upgrade" in content
        for alternate_guide in alternate_guides:
            assert alternate_guide in content


def test_landing_navigation_is_translated_compact_and_agents_install_is_separate() -> None:
    landing = LANDING.read_text(encoding="utf-8")

    for key in (
        "nav.whatsnew",
        "nav.problem",
        "nav.workflow",
        "nav.start",
        "nav.advanced",
        "nav.map",
        "nav.resume",
        "nav.companion",
        "nav.concepts",
        "nav.support",
    ):
        assert f'data-i18n="{key}"' in landing
        assert landing.count(f"'{key}':") == 3

    assert "Detalhes avançados de uso</a></li>" not in landing
    assert "installs by copying files" not in landing
    assert "AI-Agents/v1.1.6/scripts/install-agents-kit.sh" in landing
    assert ".companion-card .arrow-link {\n      display: block;" in landing


def test_default_agents_release_is_current_and_checksum_pinned() -> None:
    assert DEFAULT_REF == "v1.1.7"
    assert KNOWN_TARBALL_SHA256[(REPO, DEFAULT_REF)] == (
        "7bff38d6ff94576fee6329fd84074d14ad9af649e8d98ff4230516a4283db97a"
    )


def test_cli_help_uses_real_upstream_owner() -> None:
    help_text = build_parser().format_help()
    assert "github.com/EDortta/AI-Agents" in help_text
    assert "[GITHUB_OWNER]" not in help_text
