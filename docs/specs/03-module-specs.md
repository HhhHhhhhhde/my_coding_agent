# Module Specs

## CLI

输入：

- 用户任务文本。
- workspace 路径。
- 模型名。
- max_steps。
- mode，取值为 plan 或 build。

输出：

- 终端运行过程。
- 最终总结。
- trajectory 日志路径。

必须支持：

- 从环境变量读取 API key。
- 默认 workspace 为当前目录。
- 默认 max_steps 为 20。
- 默认 mode 为 build。

## Agent Loop

输入：

- 用户任务。
- 工具集合。
- 上下文管理器。
- LLM client。

输出：

- AgentResult。

核心逻辑：

```text
while not terminated:
  messages = context_manager.build_messages(state)
  raw_response = llm.complete(messages)
  action = parser.parse(raw_response)
  if parse failed:
    observation = parser_error
  else:
    observation = tools.execute(action)
  logger.record(step)
  state.update(action, observation)
  termination = should_stop(state)
```

必须处理：

- LLM 返回空内容。
- JSON 解析失败。
- 工具不存在。
- 参数错误。
- 工具执行异常。
- 命令超时。
- 重复探索或长时间不推进任务。
- 达到最大步数。

## LLM Client

输入：

- messages。
- model。
- temperature。

输出：

- 模型原始文本响应。

必须支持：

- OpenAI 兼容 chat completions 或 responses 风格接口中的一种。
- API key 通过环境变量读取。
- base_url 可通过环境变量配置。
- 调用失败时返回可诊断错误。

不负责：

- 不解析 action。
- 不执行工具。
- 不决定任务是否完成。

## Action Parser

输入：

- 模型原始文本。

输出：

- Action 或 ParseError。

Action 结构：

```json
{
  "thought": "short reasoning",
  "action": {
    "tool": "read_file",
    "args": {
      "path": "src/main.py",
      "start": 1,
      "end": 80
    }
  }
}
```

必须校验：

- 顶层必须是 JSON object。
- 必须包含 action。
- action.tool 必须是字符串。
- action.args 必须是 object。
- thought 可选但建议要求存在。

错误恢复：

- 解析失败时，将错误作为 observation 反馈给模型。
- 可恢复错误应附带 retry_hint。
- InvalidJson 且意图是写文件时，引导模型改用 content_base64。
- 不直接终止，除非连续解析失败超过上限。

## Tool Registry

输入：

- Action。

输出：

- Observation。

职责：

- 查找工具。
- 校验参数。
- 调用 safety policy。
- 执行 handler。
- 捕获异常。
- 统一包装工具结果。

Observation 结构：

```json
{
  "ok": true,
  "tool": "read_file",
  "content": "...",
  "truncated": false
}
```

失败结构：

```json
{
  "ok": false,
  "tool": "read_file",
  "error_type": "PathDenied",
  "message": "Path is outside workspace"
}
```

## File Tools

必须实现：

- list_dir(path)
- read_file(path, start, end)
- write_file(path, content)
- write_file(path, content_lines)
- write_file(path, content_base64)
- replace_in_file(path, old, new)

建议加分：

- apply_patch(patch)

共同约束：

- 路径必须在 workspace 内。
- 默认拒绝敏感文件。
- read_file 单次最多返回固定行数。
- write_file 和 replace_in_file 必须记录 modified_files。
- content、content_lines、content_base64 三种写入内容形式只能选择一种。

## Search Tools

必须实现：

- search(pattern, path)

约束：

- 只搜索 workspace 内。
- 默认忽略 .git、venv、node_modules、target、dist、build。
- 返回结果限制数量。
- 每条结果包含 path、line、text。

## Shell Tools

必须实现：

- run_shell(command)

约束：

- working directory 固定为 workspace。
- 默认超时 30 秒。
- 输出最多保留固定字符数。
- 返回 exit_code、stdout、stderr、duration。
- 高风险命令拒绝或确认。

## Diff Tools

建议实现：

- git_diff()

约束：

- 如果 workspace 不是 git repo，返回明确说明。
- 不自动 stage、commit、push。

## Context Manager

输入：

- AgentState。
- Tool specs。
- Project summary。

输出：

- messages。

必须包含：

- 系统提示词。
- 用户原始任务。
- 当前模式。
- 可用工具说明。
- 最近 action/observation。
- 必要的项目摘要。
- inspected_paths。
- exploration_streak。

压缩策略：

- 保留最近 6 轮原始历史。
- 更早历史压缩成摘要。
- 始终保留已修改文件和验证结果。

## Safety Policy

必须检查：

- 路径是否位于 workspace 内。
- 是否访问敏感文件。
- 是否执行危险命令。
- 是否输出过大。
- 是否超时。

默认危险命令：

- rm -rf
- del /s
- rmdir /s
- git push
- git reset --hard
- curl | sh
- powershell Invoke-Expression

## Verifier

职责：

- 记录 run_shell 中疑似测试或构建命令的结果。
- finish 前检查是否已有验证。
- 如果没有验证，提示模型继续验证或说明原因。

## Trajectory Logger

日志格式：

- JSONL。
- 一行一条事件。

必须记录：

- step。
- timestamp。
- raw_model_response。
- parsed_action。
- observation。
- error。
- modified_files。
- termination_reason。
