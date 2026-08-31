# My Coding Agent

一个从零实现的编程智能体项目。它的目标是通过与大语言模型交互，在本地工作区内自主读取文件、搜索代码、修改文件、执行命令，并根据运行结果持续迭代，完成真实编程任务。

本项目已完成 Milestone 1-3 的主体能力：自研 agent loop、JSON action 协议、本地文件/搜索/命令工具、轨迹日志、Plan / Build 双模式、会话上下文、上下文压缩、错误恢复提示、progress guard、workspace 权限边界、敏感文件保护和 shell 风险控制。CLI 还提供了一个零依赖文字交互界面，用于启动后输入任务并选择 plan/build 模式。

## 题目约束

- 不封装 Claude Code、Codex、OpenCode、DeepSeek Harness 等现成 coding agent 产品。
- 不使用 LangChain、LlamaIndex、OpenAI Agents SDK、Claude Agent SDK、AutoGen、CrewAI 等 agent 框架。
- 允许使用模型厂商 API 客户端、OpenAI 兼容网关和模型原生能力。
- 不依赖服务端托管的代码执行或文件工具。
- API key 等凭据只通过环境变量或未入库配置提供。

## 设计目标

本项目希望实现一个足够小、足够清楚、可以解释清楚每个设计决策的 coding agent。相比追求复杂功能，当前更重视以下几点：

- agent loop 必须自研。
- 工具协议和模型输出解析必须自研。
- 本地文件和命令执行需要逐步补齐安全边界。
- 每一步 action 和 observation 必须可记录、可复盘。
- agent 完成任务前应尽量运行测试或检查命令完成验证。

## 核心架构

```text
User / CLI
  -> Agent Loop
    -> Context Manager
    -> LLM Client
    -> Action Parser
    -> Tool Registry
      -> File Tools
      -> Search Tools
      -> Shell Tools
      -> Diff Tools
    -> Safety Policy
    -> Trajectory Logger
    -> Verifier
```

核心思想是：LLM 只负责提出下一步动作，本地程序负责解析、校验、执行和记录。模型不会直接获得文件系统或 shell 权限。

## MVP 必做功能

- 多轮 agent loop：已完成。
- 自研 JSON action 协议：已完成。
- 目录查看和按行读取文件：已完成。
- 代码搜索：已完成。
- 文件创建和精确修改：已完成。
- 本地命令执行：已完成。
- 命令超时和输出截断：已完成。
- 安全边界：已完成首版，包含 workspace 限制、敏感文件拒绝和 shell 风险分级。
- 运行轨迹日志：已完成。
- 完成总结和验证记录：已完成。

## 加分功能候选

- Plan / Build 双模式：已完成。Plan 模式只注册读、搜和 finish，Build 模式允许修改和执行。
- 上下文压缩：已完成。保留最近步骤，压缩早期 observation，并保存重要说明文件工作笔记。
- 高风险操作确认：已完成首版。覆盖已有文件、安装依赖、联网等 review 级操作会请求确认；危险命令直接拒绝。
- 完整 safety policy：已完成首版。workspace 越界拒绝、敏感文件拒绝、危险 shell 命令治理。
- 轻量 repo map：扫描项目文件树和关键符号，减少盲目读取。
- apply_patch 编辑工具：用 patch 方式做更精确的代码修改。
- 验证门禁：finish 前要求测试、构建或说明无法验证。
- 轨迹回放：把 JSONL 运行日志转成人类可读报告。

## 运行方式

先复制 `.env.example` 为本地 `.env`，并填入自己的 API key。`.env` 不会入库。

如果模型响应长时间没有返回，可以通过 `.env` 调整单次 LLM 请求超时：

```env
AGENT_LLM_TIMEOUT_SECONDS=60
```

如果模型在生成较大代码文件时等待过久，可以限制单次模型输出长度，让 agent 按步骤分块写入：

```env
AGENT_LLM_MAX_TOKENS=5000
```

较大的新文件会按 `write_file` + `append_file` 分块生成，每次大约 60-100 行代码。

如果 OpenAI-compatible 网关偶发返回空内容，可以配置同一步内的空响应重试次数：

```env
AGENT_LLM_EMPTY_RESPONSE_RETRIES=2
```

如果诊断日志显示 `finish_reason=length` 且 `reasoning_tokens` 接近 `AGENT_LLM_MAX_TOKENS`，说明模型把输出预算花在内部思考上了。agent 会在空响应重试时临时提高本次请求的 `max_tokens`，并追加短提示要求模型直接返回一个小 JSON action。

普通命令模式：

```bash
uv run python -m mini_agent --workspace examples/demo_calculator --max-steps 20 "请修复这个项目中的测试失败，并验证测试通过。"
```

交互启动模式：

```bash
uv run python -m mini_agent -i
```

交互模式会连续运行：每轮任务结束后会输出由 LLM 生成的一段中文 Turn Summary，然后可以继续输入新任务，或输入 `q`、`quit`、`exit` 退出。

交互模式支持轻量会话命令：

```text
/summary        查看上一轮任务总结
/history        查看最近几轮任务摘要
/clear          清空会话上下文
/mode build     切换到 build 模式
/mode plan      切换到 plan 模式
/workspace PATH 切换工作区
/maxsteps N     设置最大步数
/help           查看命令列表
```

安全机制简测：

```bash
uv run python -m mini_agent --workspace . --max-steps 3 "请读取 .env 文件内容"
uv run python -m mini_agent --workspace . --max-steps 3 "请运行 git reset --hard HEAD"
uv run python -m mini_agent -i
```

前两条应被权限策略拒绝；交互模式下安装依赖或覆盖已有文件会显示确认提示。

也可以使用安装后的脚本入口：

```bash
uv run my-coding-agent --workspace examples/demo_calculator "请修复这个项目中的测试失败，并验证测试通过。"
```

Plan 模式示例：

```bash
uv run python -m mini_agent --mode plan --workspace examples/demo_task_manager "请阅读这个项目并给出修复测试失败的计划。"
```

## 测试

```bash
uv run pytest -q
```

当前离线测试覆盖 agent loop、parser、工具协议、上下文管理、progress guard、target scope、session、CLI 展示和 milestone03 安全策略。

当前 demo 项目故意包含一个失败测试，用于视频中展示 agent 从失败到修复的过程：

```bash
uv run --extra dev pytest -q examples/demo_calculator
```

更复杂的演示项目包含多函数、多测试和多处潜在修复点：

```bash
uv run --extra dev pytest -q examples/demo_task_manager
uv run python -m mini_agent --workspace examples/demo_task_manager --max-steps 20 "请修复这个任务管理器项目中的测试失败，并验证测试通过。"
```

更复杂的 build 能力测试用例：

```bash
uv run --extra dev pytest -q examples/demo_expense_reconciler
uv run python -m mini_agent --workspace examples/demo_expense_reconciler --max-steps 30 "请实现这个费用对账示例中的核心函数，并让当前目录下的测试通过。"
```

复杂 plan 能力测试用例：

```bash
uv run python -m mini_agent --mode plan --workspace examples/plan_alarm_core_architecture --plan-output-dir ../../plans "请阅读这个 brief，并输出定时闹钟核心模块架构计划。"
```

## 当前文档

- `docs/specs/01-requirements.md`：需求、必做功能、加分功能和不做范围。
- `docs/specs/02-architecture.md`：总体架构和关键取舍。
- `docs/specs/03-module-specs.md`：模块级输入、输出和职责。
- `docs/specs/04-tool-protocol.md`：JSON action 工具协议。
- `docs/specs/05-safety-policy.md`：workspace、安全命令和敏感文件策略。
- `docs/specs/06-context-management.md`：上下文组成和压缩策略。
- `docs/specs/07-demo-scenario.md`：视频演示任务设计。

## 计划

当前已完成 Milestone 1-3 的主体实现。下一阶段进入 Milestone 4 和交付收尾：补齐轨迹回放/报告、README.txt 精简版、演示脚本和可录屏 demo。

详细计划见：

- `docs/plans/roadmap.md`
- `docs/plans/milestone-1-mvp.md`
- `docs/plans/milestone-2-context-management.md`
- `docs/plans/milestone-3-reliability-safety.md`
- `docs/plans/milestone-4-observability-knowledge.md`
