# Project Roadmap

## Milestone Overview

1. Milestone 1: MVP Agent Loop
   - 目标：跑通自研 coding agent 的最小闭环。
   - 关键词：CLI、LLM client、JSON action、tools、agent loop、trajectory。
   - 状态：已完成。

2. Milestone 2: Context Management
   - 目标：让连续交互具备会话感，并管理上下文预算。
   - 关键词：session state、session context、`/clear`、history、context priority。
   - 状态：已完成首版。

3. Milestone 3: Reliability And Safety
   - 目标：让 agent 失败后能恢复，并具备明确权限边界。
   - 关键词：error taxonomy、retry policy、progress guard、permission control、confirmation。
   - 状态：已完成首版。

4. Milestone 4: Observability And Knowledge
   - 目标：让行为可复盘、可解释。
   - 关键词：structured logs、report、replay。
   - 状态：轨迹回放与 Markdown 报告已完成首版。

5. Lightweight Skills
   - 目标：让用户可以把可复用工作方式写成本地 SKILL.md，并在交互会话中持久启用。
   - 关键词：workspace skills、active skill context、interactive commands、agent-authored skills。
   - 状态：已完成首版。

## Design Principle

每个 milestone 都必须保留一个清楚的架构主题：

- Milestone 1 证明 agent loop 是自研且可运行的。
- Milestone 2 证明 agent 能管理上下文，而不是只靠一次 prompt。
- Milestone 3 证明 agent runtime 有可靠性和权限意识。
- Milestone 4 证明 agent 行为可观测、可回放。

## Current Priority

当前优先级是考核交付定稿：README.md、README.txt、核心 docs 和 2 分钟测试流程已经对齐现有功能，接下来只做必要修正与演示稳定性检查。
