from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .safety import is_path_inside_workspace, is_sensitive_path


MAX_SKILL_CHARS = 4000
DEFAULT_SKILLS_DIR = "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path
    content: str


class SkillSession:
    def __init__(self) -> None:
        self.active: dict[str, Skill] = {}

    def activate(self, skill: Skill) -> None:
        self.active[skill.name] = skill

    def remove(self, name: str) -> bool:
        key = normalize_skill_name(name)
        if key not in self.active:
            return False
        del self.active[key]
        return True

    def clear(self) -> None:
        self.active.clear()

    def names(self) -> list[str]:
        return list(self.active)

    def prompt_context(self) -> str:
        return format_active_skills(list(self.active.values()))

    def status_text(self) -> str:
        if not self.active:
            return "当前没有启用 skill。"
        lines = ["已启用 skill："]
        for skill in self.active.values():
            lines.append(f"- {skill.name}: {skill.path}")
        return "\n".join(lines)


def discover_skills(workspace: Path, skills_dir: str = DEFAULT_SKILLS_DIR) -> list[Skill]:
    root = resolve_skills_root(workspace, skills_dir)
    if not root.exists():
        return []
    paths = sorted(
        [path for path in root.rglob("*") if path.is_file() and path.name.lower() == "skill.md"],
        key=lambda path: str(path).lower(),
    )
    skills: list[Skill] = []
    for path in paths:
        try:
            skills.append(load_skill_from_path(workspace, path))
        except (OSError, ValueError):
            continue
    return skills


def load_skill(workspace: Path, value: str, skills_dir: str = DEFAULT_SKILLS_DIR) -> Skill:
    query = value.strip()
    if not query:
        raise ValueError("Skill name or path is required.")

    root = resolve_skills_root(workspace, skills_dir)
    candidates = [
        root / query / "SKILL.md",
        root / query / "skill.md",
        root / query,
        workspace / query,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return load_skill_from_path(workspace, candidate)

    normalized = normalize_skill_name(query)
    for skill in discover_skills(workspace, skills_dir):
        if skill.name == normalized:
            return skill
    raise FileNotFoundError(f"Skill not found: {value}")


def load_skill_from_path(workspace: Path, path: Path) -> Skill:
    resolved = path.resolve()
    if not is_path_inside_workspace(resolved, workspace.resolve()):
        raise ValueError(f"Skill path is outside workspace: {resolved}")
    if is_sensitive_path(resolved):
        raise ValueError(f"Skill path looks sensitive: {resolved}")
    if resolved.name.lower() != "skill.md":
        raise ValueError(f"Skill file must be named SKILL.md: {resolved}")
    content = resolved.read_text(encoding="utf-8", errors="replace").strip()
    if not content:
        raise ValueError(f"Skill file is empty: {resolved}")
    return Skill(name=skill_name_from_path(resolved), path=resolved, content=content[:MAX_SKILL_CHARS])


def create_skill_template(workspace: Path, name: str, skills_dir: str = DEFAULT_SKILLS_DIR) -> Path:
    slug = normalize_skill_name(name)
    if not slug:
        raise ValueError("Skill name must contain letters, numbers, '_' or '-'.")
    root = resolve_skills_root(workspace, skills_dir)
    path = root / slug / "SKILL.md"
    if path.exists():
        raise FileExistsError(f"Skill already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    title = slug.replace("-", " ").replace("_", " ").title()
    content = (
        f"# {title}\n\n"
        "## When To Use\n\n"
        "- Use this skill when the user explicitly asks for this workflow.\n\n"
        "## Instructions\n\n"
        "- State the goal before acting.\n"
        "- Prefer the project's existing patterns.\n"
        "- Keep changes focused and verify the result.\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def format_skill_list(skills: list[Skill]) -> str:
    if not skills:
        return "未找到 skill。默认目录是 skills/<name>/SKILL.md。"
    return "\n".join(f"- {skill.name}: {skill.path}" for skill in skills)


def format_active_skills(skills: list[Skill]) -> str:
    if not skills:
        return ""
    sections = ["Active Skills:"]
    for skill in skills:
        sections.append(f"\n## {skill.name}\nSource: {skill.path}\n{skill.content}")
    return "\n".join(sections)


def resolve_skills_root(workspace: Path, skills_dir: str) -> Path:
    root = Path(skills_dir)
    if not root.is_absolute():
        root = workspace / root
    return root.resolve()


def skill_name_from_path(path: Path) -> str:
    parent = path.parent.name
    return normalize_skill_name(parent or path.stem)


def normalize_skill_name(name: str) -> str:
    text = name.strip().replace("\\", "/").rstrip("/")
    text = text.split("/")[-1]
    text = text.removesuffix(".md").removesuffix(".MD")
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", text.lower()).strip("-_")
    return normalized
