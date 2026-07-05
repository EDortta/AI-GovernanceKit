from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from governancekit import install_agents as ia


def _make_tar(members: dict) -> tarfile.TarFile:
    buf = io.BytesIO()
    tf = tarfile.open(fileobj=buf, mode="w")
    for name, data in members.items():
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    tf.close()
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r")


class SafeExtractallTests(unittest.TestCase):
    def test_extracts_normal_members(self) -> None:
        tf = _make_tar({"pkg/file.txt": b"hello\n"})
        with tempfile.TemporaryDirectory() as d, tf:
            dest = Path(d)
            ia._safe_extractall(tf, dest)
            self.assertEqual((dest / "pkg" / "file.txt").read_text(), "hello\n")

    def test_rejects_path_traversal_member(self) -> None:
        tf = _make_tar({"../evil.txt": b"pwned\n"})
        with tempfile.TemporaryDirectory() as d, tf:
            dest = Path(d) / "sub"
            dest.mkdir()
            with self.assertRaises((RuntimeError, tarfile.OutsideDestinationError, tarfile.TarError)):
                ia._safe_extractall(tf, dest)
            self.assertFalse((Path(d) / "evil.txt").exists())

    def test_absolute_path_member_stays_inside_dest(self) -> None:
        # The stdlib "data" filter sanitizes absolute names (strips leading "/")
        # rather than raising — assert the escape is neutralized either way.
        tf = _make_tar({"/etc/evil.txt": b"pwned\n"})
        with tempfile.TemporaryDirectory() as d, tf:
            dest = Path(d)
            try:
                ia._safe_extractall(tf, dest)
            except (RuntimeError, tarfile.TarError):
                pass
            self.assertFalse(Path("/etc/evil.txt").exists())
            for path in dest.rglob("*"):
                self.assertTrue(str(path.resolve()).startswith(str(dest.resolve())))


if __name__ == "__main__":
    unittest.main()
