from __future__ import annotations

import io
import tarfile
from contextlib import redirect_stderr
from pathlib import Path

from governancekit import install_agents


def test_development_download_warning_explains_unpinned_mutable_ref(tmp_path: Path, monkeypatch) -> None:
    def fake_urlretrieve(_url: str, archive: Path):
        source = tmp_path / "payload"
        source.mkdir(exist_ok=True)
        (source / "README.md").write_text("dev\n", encoding="utf-8")
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(source, arcname="AI-Agents-dev")
        return str(archive), None

    monkeypatch.setattr(install_agents.urllib.request, "urlretrieve", fake_urlretrieve)

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        extracted = install_agents._download(
            install_agents.REPO,
            install_agents.DEVELOPMENT_REF,
            tmp_path / "download",
            allow_unverified=True,
        )

    output = stderr.getvalue()
    assert extracted.is_dir()
    assert "Development AI-Agents ref:" in output
    assert "no pinned checksum exists for this mutable development ref" in output
    assert "development mode explicitly accepts an unpinned ref" in output
    assert "--allow-unverified was given" not in output
