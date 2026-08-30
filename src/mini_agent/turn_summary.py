from __future__ import annotations

from pathlib import Path

from .protocol import AgentResult


TURN_SUMMARY_SYSTEM_PROMPT = """You are the coding agent speaking directly to the user after finishing one turn.

Output requirements:
- Write in Chinese.
- Output exactly one continuous paragraph.
- Do not use Markdown, headings, bullets, numbered lists, tables, or code fences.
- Use first person. Say "我" when referring to the agent. Do not say "代理", "该 agent", "本轮任务", or "该任务".
- Sound like a calm coding partner reporting back, not an audit report.
- Mention what you attempted, whether it succeeded, the important file changes, the verification result, and where the trajectory or plan output is saved when useful.
- Do not say source code was read or modified unless modified_files or the finish summary proves it. If only docs were read, call them docs or design documents.
- If the result failed before any file changes, say that directly and avoid implying implementation happened.
- Prefer 2 to 4 natural sentences in one paragraph.
- Keep command names and paths accurate, but do not cram in every minor detail if it makes the paragraph stiff.
- Be concise, natural, and factual. Do not invent actions that are not in the provided data.
"""


def generate_turn_summary(llm: object, task: str, mode: str, workspace: Path, result: AgentResult) -> str:
    messages = build_turn_summary_messages(task, mode, workspace, result)
    try:
        raw_summary = llm.complete(messages)
    except Exception:
        return fallback_turn_summary(task, mode, workspace, result)

    summary = normalize_turn_summary(raw_summary)
    if not summary:
        return fallback_turn_summary(task, mode, workspace, result)
    return summary


def build_turn_summary_messages(
    task: str, mode: str, workspace: Path, result: AgentResult
) -> list[dict[str, str]]:
    verification = [
        {
            "command": record.command,
            "exit_code": record.exit_code,
            "passed": record.passed,
        }
        for record in result.verification_records
    ]
    user_content = f"""Task: {task}
Mode: {mode}
Workspace: {workspace}
Success: {result.success}
Termination reason: {result.termination_reason}
Agent finish summary: {result.summary or "none"}
Modified files: {", ".join(result.modified_files) if result.modified_files else "none"}
Verification records: {verification if verification else "none"}
Plan output path: {result.output_path or "none"}
Trajectory path: {result.trajectory_path}
"""
    return [
        {"role": "system", "content": TURN_SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def normalize_turn_summary(raw_summary: str) -> str:
    lines = [line.strip().lstrip("-*0123456789.、 ") for line in raw_summary.splitlines() if line.strip()]
    return " ".join(lines).strip()


def fallback_turn_summary(task: str, mode: str, workspace: Path, result: AgentResult) -> str:
    status = "成功完成" if result.success else "已经停止"
    modified = f"修改了 {'、'.join(result.modified_files)}" if result.modified_files else "没有修改文件"
    verification = format_verification(result)
    output = f"，计划或产物已保存到 {result.output_path}" if result.output_path else ""
    agent_summary = result.summary or "没有额外总结"
    return (
        f"我刚才在 {mode} 模式下处理了“{task}”，工作区是 {workspace}，结果是{status}。"
        f"我{modified}，验证情况是：{verification}{output}。"
        f"运行轨迹保存在 {result.trajectory_path}。补充说明：{agent_summary}"
    )


def format_verification(result: AgentResult) -> str:
    if not result.verification_records:
        return "没有记录验证命令"
    return "；".join(
        f"{record.command} -> {'passed' if record.passed else 'failed'} ({record.exit_code})"
        for record in result.verification_records
    )
