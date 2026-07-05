from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
