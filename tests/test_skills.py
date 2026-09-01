from pathlib import Path

import pytest

from mini_agent.skills import (
    SkillSession,
    create_skill_template,
    discover_skills,
    format_active_skills,
    load_skill,
    normalize_skill_name,
)


def test_discover_and_load_workspace_skills(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "python-testing" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Python Testing\n\nUse pytest carefully.\n", encoding="utf-8")

    skills = discover_skills(tmp_path)
    loaded = load_skill(tmp_path, "python-testing")

    assert [skill.name for skill in skills] == ["python-testing"]
    assert loaded.name == "python-testing"
    assert "pytest carefully" in loaded.content


def test_skill_session_keeps_active_skills_until_removed(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "safety-review" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Safety Review\n\nCheck shell risk.\n", encoding="utf-8")
    session = SkillSession()

    session.activate(load_skill(tmp_path, "safety-review"))

    assert session.names() == ["safety-review"]
    assert "Check shell risk" in session.prompt_context()
    assert session.remove("safety-review")
    assert session.names() == []


def test_create_skill_template_writes_default_skill_file(tmp_path: Path) -> None:
    path = create_skill_template(tmp_path, "Bug Fixing")

    assert path == tmp_path / "skills" / "bug-fixing" / "SKILL.md"
    assert "## When To Use" in path.read_text(encoding="utf-8")
    assert load_skill(tmp_path, "bug-fixing").name == "bug-fixing"


def test_load_skill_rejects_non_skill_file(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "notes.txt"
    path.parent.mkdir()
    path.write_text("not a skill", encoding="utf-8")

    with pytest.raises(ValueError):
        load_skill(tmp_path, "skills/notes.txt")


def test_format_active_skills_includes_sources(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "compact-planner" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Compact Planner\n\nKeep it small.\n", encoding="utf-8")
    skill = load_skill(tmp_path, "compact-planner")

    text = format_active_skills([skill])

    assert "Active Skills" in text
    assert "compact-planner" in text
    assert "Keep it small" in text


def test_normalize_skill_name() -> None:
    assert normalize_skill_name("Python Testing") == "python-testing"
    assert normalize_skill_name("skills/safety-review") == "safety-review"
