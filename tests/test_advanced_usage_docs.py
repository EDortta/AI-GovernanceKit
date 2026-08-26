from __future__ import annotations

import re

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


def test_credentials_allow_symlinks_is_an_interactive_scope_option() -> None:
    args = build_parser().parse_args(
        ["config-session", "start", "--interactive", "--credentials-allow-symlinks"]
    )

    assert args.credentials_allow_symlinks is True


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
    # AC-30 retired the shell installer; the landing must not teach a curl|bash of
    # it (the ecosystem's own security-standards.md forbids curl|bash, and the tag
    # the pill pinned still serves the second-writer script AC-6/AC-10 documented).
    # This line used to assert the pill EXISTS — the test was pinning the defect.
    assert "install-agents-kit.sh" not in landing
    assert "governancekit --root . install-agents" in landing
    assert ".companion-card .arrow-link {\n      display: block;" in landing


def test_default_agents_release_is_current_and_checksum_pinned() -> None:
    """The pinned release must be verifiable and the docs must agree with it.

    This asserted the literal `v1.1.7` and its literal digest, so every bump broke the
    test instead of being checked by it — and a stale DEFAULT_REF (which is how the
    withdrawn email contract kept reinstalling itself) would have passed happily for as
    long as nobody edited the string. The property is what matters: whatever ref is
    pinned has a checksum, and every install command the docs hand a user names it.
    """
    assert (REPO, DEFAULT_REF) in KNOWN_TARBALL_SHA256, (
        f"DEFAULT_REF {DEFAULT_REF} has no entry in KNOWN_TARBALL_SHA256 — an install "
        f"would download it unverified"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", KNOWN_TARBALL_SHA256[(REPO, DEFAULT_REF)])

    for page in ("docs/index.html", "docs/advanced-usage.html",
                 "docs/advanced-usage-ptbr.html", "docs/advanced-usage-es.html"):
        text = (ROOT / page).read_text(encoding="utf-8")
        stale = re.findall(r"v1\.\d+\.\d+", text)
        assert set(stale) <= {DEFAULT_REF}, (
            f"{page} names {sorted(set(stale) - {DEFAULT_REF})} while DEFAULT_REF is "
            f"{DEFAULT_REF} — the command a user copies would install another release"
        )


def test_cli_help_uses_real_upstream_owner() -> None:
    help_text = build_parser().format_help()
    assert "github.com/EDortta/AI-Agents" in help_text
    assert "[GITHUB_OWNER]" not in help_text
