# My Coding Agent

一个从零实现的编程智能体项目。它的目标是通过与大语言模型交互，在本地工作区内自主读取文件、搜索代码、修改文件、执行命令，并根据运行结果持续迭代，完成真实编程任务。

本项目已完成 Milestone 1 的基础链路：CLI、LLM 接入、JSON action 解析、工具注册、文件工具、搜索工具、命令执行工具、agent loop、轨迹日志、demo 项目和离线测试。CLI 还提供了一个零依赖文字交互界面，用于启动后输入任务并选择 plan/build 模式。

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
- 运行轨迹日志：已完成。
- 完成总结和验证记录：已完成。

## 加分功能候选

- Plan / Build 双模式：已完成轻量版。Plan 模式只注册读、搜和 finish，Build 模式允许修改和执行。
- 轻量 repo map：扫描项目文件树和关键符号，减少盲目读取。
- apply_patch 编辑工具：用 patch 方式做更精确的代码修改。
- 验证门禁：finish 前要求测试、构建或说明无法验证。
- 轨迹回放：把 JSONL 运行日志转成人类可读报告。
- 高风险操作确认：删除、覆盖、安装依赖等操作需要额外确认。
- 完整 safety policy：workspace 越界拒绝、敏感文件拒绝、危险命令治理。

## 运行方式

先复制 `.env.example` 为本地 `.env`，并填入自己的 API key。`.env` 不会入库。

普通命令模式：

```bash
uv run python -m mini_agent --workspace examples/demo_calculator --max-steps 20 "请修复这个项目中的测试失败，并验证测试通过。"
```

交互启动模式：

```bash
uv run python -m mini_agent -i
```

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
uv run --extra dev pytest -q tests
```

当前 demo 项目故意包含一个失败测试，用于视频中展示 agent 从失败到修复的过程：

```bash
uv run --extra dev pytest -q examples/demo_calculator
```

更复杂的演示项目包含多函数、多测试和多处潜在修复点：

```bash
uv run --extra dev pytest -q examples/demo_task_manager
uv run python -m mini_agent --workspace examples/demo_task_manager --max-steps 20 "请修复这个任务管理器项目中的测试失败，并验证测试通过。"
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

第一阶段已完成基础链路和轻量 Plan / Build。第二阶段再补充完整 safety policy、git diff、验证门禁、repo map 和轨迹回放等加分功能。

详细计划见：

- `docs/plans/milestone-1-mvp.md`
- `docs/plans/milestone-2-quality.md`
