# Milestone 4: Observability And Replay

## 状态

已完成轨迹回放与 Markdown 报告首版。

## 目标

让 agent 的行为可复盘、可解释。

这一阶段包括结构化日志、轨迹回放和报告生成。用户可以从命令行或交互模式查看最近运行，也可以把 JSONL trajectory 转成 Markdown 报告。

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
   - 支持 `latest`、序号和具体 JSONL 路径。
   - 交互模式提供 `/runs`、`/replay latest`、`/replay N` 和 `/replay PATH`。
   - 状态：已完成。

4. Replay Hygiene
   - 报告只复盘本地 trajectory 已记录的信息。
   - 敏感文件仍由 safety policy 在工具层拒绝。
   - 报告包含来源 trajectory 路径，便于定位原始日志。

## 验收标准

1. 给定一条 trajectory，可以生成可读 Markdown 报告。
2. 失败任务报告能指出失败阶段和主要错误类型。
3. 用户可以在交互模式列出最近轨迹。
4. 用户可以在交互模式查看最新轨迹或指定轨迹。
5. replay 输出包含任务、步骤、修改文件、验证命令和最终总结。

## 使用方式

```bash
uv run python -m mini_agent --workspace . --replay latest
uv run python -m mini_agent --workspace . --replay latest --replay-output reports/latest-run.md
```

也可以把 `latest` 换成具体 JSONL 路径。

## 取舍原则

1. 可读性优先于格式复杂度。
2. 命令行和交互模式复用同一套 replay 生成逻辑。
3. 报告必须保留来源路径，方便回到原始 JSONL。

## 非目标

- 大规模向量数据库。
- 自动联网抓取外部知识。
- 无来源的长期记忆。
- 替代人工代码审查。
