from governancekit.adoption import apply_adoption_proposal, build_adoption_proposal


def test_generated_adoption_is_evidence_based_and_sets_readiness(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    proposal = build_adoption_proposal(tmp_path)
    written = apply_adoption_proposal(proposal)
    assert written == [".docs/software-overview.md", ".docs/limits.md"]
    assert "project_context_ready: yes" in (tmp_path / ".docs/software-overview.md").read_text()
    assert "limits_ready: yes" in (tmp_path / ".docs/limits.md").read_text()


def test_adoption_never_overwrites_complete_project_documents(tmp_path) -> None:
    docs = tmp_path / ".docs"
    docs.mkdir()
    (docs / "software-overview.md").write_text("project_context_ready: yes\ncustom\n")
    (docs / "limits.md").write_text("limits_ready: yes\ncustom\n")
    assert apply_adoption_proposal(build_adoption_proposal(tmp_path)) == []
    assert "custom" in (docs / "software-overview.md").read_text()
