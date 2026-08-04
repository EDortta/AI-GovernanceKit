from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from governancekit import install_agents as ia


def _write_fake_archive(dest: Path, content: bytes) -> None:
    dest.write_bytes(content)


class DefaultRefPinTests(unittest.TestCase):
    def test_default_ref_is_not_the_mutable_main_branch(self) -> None:
        # SEC-0105: a mutable default ref means every install trusts whatever
        # is on "main" at download time, with no way to verify it.
        self.assertNotEqual(ia.DEFAULT_REF, "main")

    def test_default_repo_ref_has_a_known_checksum(self) -> None:
        self.assertIn((ia.REPO, ia.DEFAULT_REF), ia.KNOWN_TARBALL_SHA256)

    def test_amazon_q_adapter_is_installed_and_upgraded(self) -> None:
        adapter = ".amazonq/rules/ai-agents.md"
        self.assertIn(adapter, ia._FRESH_PATHS)
        self.assertIn(adapter, ia._UPGRADE_PATHS)


class DownloadChecksumTests(unittest.TestCase):
    def test_matching_checksum_is_accepted(self) -> None:
        # Not a real gzip tarball, so extraction fails with ReadError — but that
        # proves checksum verification passed (a mismatch raises RuntimeError
        # with a different message before tarfile.open is ever reached).
        content = b"totally-a-tarball"
        sha = __import__("hashlib").sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(
            ia.KNOWN_TARBALL_SHA256, {("acme/kit", "v9"): sha}
        ), mock.patch(
            "governancekit.install_agents.urllib.request.urlretrieve",
            side_effect=lambda url, path: _write_fake_archive(Path(path), content),
        ):
            with self.assertRaises(tarfile.ReadError):
                ia._download("acme/kit", "v9", Path(d))

    def test_mismatched_checksum_is_rejected_before_extraction(self) -> None:
        content = b"totally-a-tarball"
        wrong_sha = "0" * 64
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(
            ia.KNOWN_TARBALL_SHA256, {("acme/kit", "v9"): wrong_sha}
        ), mock.patch(
            "governancekit.install_agents.urllib.request.urlretrieve",
            side_effect=lambda url, path: _write_fake_archive(Path(path), content),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                ia._download("acme/kit", "v9", Path(d))
            self.assertIn("Checksum mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


def test_unknown_checksum_refuses_instead_of_warning(tmp_path, monkeypatch):
    # A warning printed into a verbose install is not a decision anyone made.
    import governancekit.install_agents as ia

    monkeypatch.setattr(ia.urllib.request, "urlretrieve", lambda url, dest: Path(dest).write_bytes(b"x"))

    with pytest.raises(RuntimeError, match="No known checksum"):
        ia._download("someone/fork", "main", tmp_path)


def test_unknown_checksum_installs_when_explicitly_allowed(tmp_path, monkeypatch):
    import tarfile

    import governancekit.install_agents as ia

    payload = tmp_path / "payload"
    (payload / "AI-Agents-main").mkdir(parents=True)
    (payload / "AI-Agents-main" / "AGENTS.md").write_text("kit\n", encoding="utf-8")

    def fake_retrieve(url, dest):
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(payload / "AI-Agents-main", arcname="AI-Agents-main")

    monkeypatch.setattr(ia.urllib.request, "urlretrieve", fake_retrieve)
    target = tmp_path / "dl"
    target.mkdir()

    extracted = ia._download("someone/fork", "main", target, allow_unverified=True)

    assert (extracted / "AGENTS.md").read_text() == "kit\n"


def test_several_top_level_directories_are_refused(tmp_path, monkeypatch):
    import tarfile

    import governancekit.install_agents as ia

    payload = tmp_path / "payload"
    for name in ("one", "two"):
        (payload / name).mkdir(parents=True)
        (payload / name / "f.txt").write_text("x", encoding="utf-8")

    def fake_retrieve(url, dest):
        with tarfile.open(dest, "w:gz") as tf:
            for name in ("one", "two"):
                tf.add(payload / name, arcname=name)

    monkeypatch.setattr(ia.urllib.request, "urlretrieve", fake_retrieve)
    target = tmp_path / "dl"
    target.mkdir()

    with pytest.raises(RuntimeError, match="several top-level directories"):
        ia._download("someone/fork", "main", target, allow_unverified=True)
