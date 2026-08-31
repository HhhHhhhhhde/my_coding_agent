from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SENSITIVE_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
SENSITIVE_NAME_RE = re.compile(r"(?:^|[._-])(key|token|secret|credential|credentials|password|passwd)(?:$|[._-])", re.I)


@dataclass(frozen=True)
class ShellRisk:
    level: str
    reason: str


def is_path_inside_workspace(path: Path, workspace: Path) -> bool:
    try:
        path.resolve().relative_to(workspace.resolve())
    except ValueError:
        return False
    return True


def is_sensitive_path(path: Path) -> bool:
    lowered_parts = [part.lower() for part in path.parts]
    if any(part in SENSITIVE_FILE_NAMES for part in lowered_parts):
        return True
    return any(SENSITIVE_NAME_RE.search(part) for part in lowered_parts)


def classify_shell_command(command: str) -> ShellRisk:
    normalized = command.strip().lower()
    if not normalized:
        return ShellRisk("blocked", "empty shell command")

    if reads_sensitive_file(normalized):
        return ShellRisk("blocked", "command appears to read a sensitive file")
    if modifies_git_history(normalized):
        return ShellRisk("blocked", "command can modify git history")
    if deletes_directory(normalized):
        return ShellRisk("blocked", "command can delete files or directories")
    if installs_dependencies(normalized):
        return ShellRisk("review", "command can install dependencies")
    if uses_network(normalized):
        return ShellRisk("review", "command appears to access the network")
    if generates_many_files(normalized):
        return ShellRisk("review", "command may generate many files")
    return ShellRisk("safe", "command is allowed")


def reads_sensitive_file(command: str) -> bool:
    return bool(re.search(r"(\.env|id_rsa|id_ed25519|\btoken\b|\bsecret\b|\bcredential)", command))


def modifies_git_history(command: str) -> bool:
    return bool(re.search(r"\bgit\s+(reset|rebase|filter-branch|push\s+.*--force)", command))


def deletes_directory(command: str) -> bool:
    patterns = [
        r"\brm\s+.*-[^\n]*r",
        r"\brmdir\b",
        r"\bremove-item\b.*(?:^|\s)-recurse(?:\s|$)",
        r"\bdel\s+/[sq]\b",
        r"\brd\s+/[sq]\b",
    ]
    return any(re.search(pattern, command) for pattern in patterns)


def installs_dependencies(command: str) -> bool:
    patterns = [
        r"\b(pip|pip3)\s+install\b",
        r"\buv\s+add\b",
        r"\buv\s+pip\s+install\b",
        r"\bpoetry\s+add\b",
        r"\bnpm\s+(install|i|add)\b",
        r"\bpnpm\s+(install|add)\b",
        r"\byarn\s+(add|install)\b",
        r"\bcargo\s+install\b",
    ]
    return any(re.search(pattern, command) for pattern in patterns)


def uses_network(command: str) -> bool:
    return bool(re.search(r"\b(curl|wget|invoke-webrequest|iwr|fetch)\b", command))


def generates_many_files(command: str) -> bool:
    return bool(re.search(r"\b(npm|pnpm|yarn)\s+run\s+(build|generate|codegen)\b", command))
