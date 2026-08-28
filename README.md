# My Coding Agent

一个从零实现的编程智能体项目。它的目标是通过与大语言模型交互，在本地工作区内自主读取文件、搜索代码、修改文件、执行命令，并根据运行结果持续迭代，完成真实编程任务。

本项目处于架构和规格设计阶段，当前重点是先明确模块边界、功能取舍和安全策略，再进入 MVP 实现。

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
- 本地文件和命令执行必须有安全边界。
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

- 多轮 agent loop。
- 自研 JSON action 协议。
- 目录查看和按行读取文件。
- 代码搜索。
- 文件创建和精确修改。
- 本地命令执行。
- workspace 路径限制。
- 命令超时和输出截断。
- 运行轨迹日志。
- 完成总结和验证记录。

## 加分功能候选

- Plan / Build 双模式：Plan 模式只读分析，Build 模式允许修改和执行。
- 轻量 repo map：扫描项目文件树和关键符号，减少盲目读取。
- apply_patch 编辑工具：用 patch 方式做更精确的代码修改。
- 验证门禁：finish 前要求测试、构建或说明无法验证。
- 轨迹回放：把 JSONL 运行日志转成人类可读报告。
- 高风险操作确认：删除、覆盖、安装依赖等操作需要额外确认。

## 当前文档

- `docs/specs/01-requirements.md`：需求、必做功能、加分功能和不做范围。
- `docs/specs/02-architecture.md`：总体架构和关键取舍。
- `docs/specs/03-module-specs.md`：模块级输入、输出和职责。
- `docs/specs/04-tool-protocol.md`：JSON action 工具协议。
- `docs/specs/05-safety-policy.md`：workspace、安全命令和敏感文件策略。
- `docs/specs/06-context-management.md`：上下文组成和压缩策略。
- `docs/specs/07-demo-scenario.md`：视频演示任务设计。

## 计划

第一阶段先完成 MVP，让 agent 能在一个小型 demo 项目中修复失败测试并验证通过。第二阶段再补充 Plan / Build、git diff、验证门禁、repo map 和轨迹回放等加分功能。

详细计划见：

- `docs/plans/milestone-1-mvp.md`
- `docs/plans/milestone-2-quality.md`
