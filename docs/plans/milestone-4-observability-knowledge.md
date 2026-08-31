# Milestone 4: Observability And Knowledge

## 状态

已完成轨迹回放与 Markdown 报告首版。Run Index 与 Lightweight RAG 暂未实现，保留为后续加分项。

## 目标

让 agent 的行为可复盘、可解释，并开始利用历史任务经验辅助后续任务。

这一阶段包括日志系统升级、轨迹回放、报告生成，以及轻量 RAG。RAG 不一开始上复杂向量库，先从结构化日志和关键词检索做起。

## 必做范围

1. Structured Trajectory Schema
   - 明确定义 run_start、step、run_end 事件。
   - 每步记录 action、observation、duration、error_type。
   - 记录 workspace、mode、model、max_steps。
   - 记录 session_context 是否被注入。

2. Human-readable Reports
   - 将 JSONL trajectory 转成 Markdown 报告。
   - 报告包含任务、步骤表、修改文件、验证结果、失败原因。
   - 支持成功任务报告和失败任务报告。
   - 状态：已完成首版。

3. Replay
   - 提供 trajectory replay 命令。
   - 可以按步骤查看模型动作和工具结果。
   - 可以过滤错误步骤、文件修改步骤、验证步骤。
   - 状态：已完成基础 replay；过滤视图暂未实现。

4. Run Index
   - 按 workspace 保存历史 run 索引。
   - 记录 task、status、summary、modified_files、verification。
   - 支持按关键词搜索历史任务。
   - 状态：未实现。

5. Lightweight RAG
   - 从历史 run index 和报告中检索相似任务。
   - 使用关键词、路径、工具类型和错误类型打分。
   - 将少量相关历史经验注入 prompt。
   - 明确标记 historical context，避免混淆当前任务事实。
   - 状态：未实现。

6. Knowledge Hygiene
   - 不索引 `.env`、凭据、敏感文件。
   - 不把失败经验当成必然正确做法。
   - 历史检索结果需要包含来源 trajectory 或 report 路径。

## 验收标准

1. 给定一条 trajectory，可以生成可读 Markdown 报告。
2. 失败任务报告能指出失败阶段和主要错误类型。
3. 用户可以搜索历史任务。
4. agent 遇到相似任务时，可以看到相关历史摘要。
5. 历史上下文不会覆盖当前用户明确要求。

当前已满足第 1、2 项；第 3-5 项依赖 Run Index 和 Lightweight RAG，暂列后续。

## 使用方式

```bash
uv run python -m mini_agent --workspace . --replay latest
uv run python -m mini_agent --workspace . --replay latest --replay-output reports/latest-run.md
```

也可以把 `latest` 换成具体 JSONL 路径。

## 取舍原则

1. 先做结构化日志，再做 RAG。
2. 先做关键词检索，再考虑 embedding。
3. 所有历史知识都必须有来源路径。
4. 可解释性优先于检索复杂度。

## 非目标

- 大规模向量数据库。
- 自动联网抓取外部知识。
- 无来源的长期记忆。
- 替代人工代码审查。
