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
   - 目标：让行为可复盘、可解释，并利用历史任务经验。
   - 关键词：structured logs、report、replay、run index、lightweight RAG。
   - 状态：轨迹回放与 Markdown 报告已完成首版，run index 和 lightweight RAG 未实现。

## Design Principle

每个 milestone 都必须保留一个清楚的架构主题：

- Milestone 1 证明 agent loop 是自研且可运行的。
- Milestone 2 证明 agent 能管理上下文，而不是只靠一次 prompt。
- Milestone 3 证明 agent runtime 有可靠性和权限意识。
- Milestone 4 证明 agent 行为可观测，并能从历史轨迹中提取经验。

## Current Priority

下一阶段优先进入考核交付收尾：准备 1000 汉字以内的 README.txt、2 分钟演示脚本和稳定 demo 命令。Run index、lightweight RAG、Repo map、apply_patch 工具和更严格的验证门禁作为后续加分项排期。
