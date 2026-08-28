# Architecture Spec

## 总体架构

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

## 设计原则

1. LLM 只负责提出下一步动作，不直接执行本地操作。
2. 本地程序负责解析、校验、执行和记录。
3. 所有工具必须经过统一注册和安全策略检查。
4. 每轮循环都产生可复盘的 action 和 observation。
5. 功能优先保证闭环可用，再考虑加分扩展。

## 模块职责

### CLI

负责接收用户任务和运行参数，例如 workspace、model、max_steps、mode。CLI 不包含 agent 决策逻辑。

### Agent Loop

负责调度一次完整任务。它维护步骤计数、调用 LLM、执行工具、处理错误和判断终止条件。

核心状态：

- user_task
- current_mode
- step_count
- conversation_history
- modified_files
- verification_records
- consecutive_errors

终止条件：

- 模型调用 finish。
- 达到 max_steps。
- 连续工具错误达到上限。
- 用户中断。
- LLM 响应无法恢复。

### LLM Client

负责对接 OpenAI 兼容接口或模型厂商 API。它只暴露一个简单方法，不向其他模块泄露厂商细节。

### Action Parser

负责把模型输出解析为结构化 Action。解析失败不会直接崩溃，而是生成错误 observation 反馈给模型。

### Tool Registry

负责维护可用工具列表、工具描述、参数 schema 和 handler。Agent Loop 只通过 Tool Registry 调用工具。

### Safety Policy

负责检查路径、命令、文件大小、敏感文件和高风险操作。Safety Policy 是 LLM 和本地系统之间的权限边界。

### Context Manager

负责构造每次发给 LLM 的上下文，包括 system prompt、用户任务、工具说明、项目摘要、最近历史和压缩摘要。

### Verifier

负责记录测试、构建或检查命令的结果，并在 finish 前判断是否已有足够验证。

### Trajectory Logger

负责记录每一步的输入、输出、工具调用、错误和终止原因。日志格式优先使用 JSONL。

## 推荐运行流程

1. CLI 接收任务。
2. 初始化 workspace 和安全策略。
3. 扫描基础项目摘要。
4. 构造第一轮 prompt。
5. LLM 输出 JSON action。
6. Action Parser 校验 action。
7. Safety Policy 审查工具参数。
8. Tool Registry 执行工具。
9. Observation 写入历史和轨迹日志。
10. 重复 5-9。
11. finish 后输出总结。

## 关键架构取舍

1. 采用自研 JSON action，而不是 agent SDK tool runtime。
   - 原因：能清楚展示输出解析、参数校验和本地执行逻辑。

2. 采用专用文件工具，而不是完全开放 shell。
   - 原因：文件任务更可控，返回结果更适合 LLM 阅读。

3. 采用 workspace 级权限边界。
   - 原因：题目要求本地执行，必须避免模型越权操作。

4. 采用简单上下文压缩，不做向量数据库。
   - 原因：当前项目规模小，复杂检索系统会分散实现重点。

5. 采用单 agent。
   - 原因：多 agent 协作难以在短时间内稳定验证，也不利于面试解释。
