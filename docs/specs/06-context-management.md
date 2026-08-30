# Context Management Spec

## 目标

让模型在有限上下文内获得完成任务所需的信息，同时避免把整个仓库和完整日志无脑塞进 prompt。

## 上下文组成

每轮发送给 LLM 的 messages 包含：

1. System prompt
   - 说明 agent 角色。
   - 说明 JSON action 协议。
   - 说明可用工具。
   - 说明安全和完成要求。

2. User task
   - 保留用户原始任务。
   - 不被摘要替换。

3. Project summary
   - workspace 路径。
   - 顶层文件树。
   - 识别到的项目类型。
   - 可选 repo map。

4. Recent history
   - 最近 N 轮 action 和 observation。
   - 默认 N = 10。

5. Long-term task summary
   - 更早步骤的 Rolling Task Summary。
   - 已修改文件。
   - 已查看路径。
   - 已运行命令。
   - 当前失败或阻塞点。
   - 下一步建议。

6. Persistent Working Notes
   - 保留本轮任务中已经读过的重要需求、设计和 brief 文件。
   - 典型文件包括 README.md、GAMEPLAY.md、DESIGN.md、REQUIREMENTS.md、SPEC.md。
   - 工作笔记放在独立 prompt 区域，不依赖 recent history 窗口。
   - 每条笔记有字符上限，超出后保留开头和结尾。
   - 当模型想重复读取已读需求文件时，应优先使用工作笔记继续行动。

7. Target-focus hints
   - 如果用户任务明确指定目标路径，应优先围绕该路径行动。
   - 如果目标目录不存在，Build 模式应创建目标文件，不应反复查看无关示例。
   - 相似示例最多查看一个，用于确认风格后就进入目标实现。

8. Target Scope
   - 用户任务明确给出路径时，启动时锁定该路径或其父目录。
   - 如果模型在探索中发现重要说明文件，则锁定该说明文件所在目录。
   - target_scope 写入 Current state，模型每轮都能看到当前目标目录。
   - target_scope 生效后，路径类工具默认只能访问目标目录内的文件。
   - 访问目标目录外的探索或编辑动作会返回 TargetScopeViolation。

## 设计文档驱动开发

当用户要求“根据文档实现”且目标目录中只有 README、GAMEPLAY、DESIGN、REQUIREMENTS、SPEC 或 brief 文件时，agent 应把这些文档视为可执行规格。

- 读完文档后应进入实现阶段，不继续全局探索项目约定。
- 新文件应创建在 target_scope 内。
- 如果缺少测试，优先生成一个小而可运行的 MVP，并用语法检查或启动命令做基础验证。
- 对游戏类文档，优先选择 Python 标准库实现，生成 `runner_game.py`、`main.py` 等常规入口文件。

## 初始项目摘要

启动时建议收集：

- 顶层目录。
- README 文件摘要。
- pyproject.toml、package.json、pom.xml 等项目配置。
- 测试目录是否存在。

不要启动时读取所有源码。

## Repo Map 加分项

可选实现轻量 repo map：

Python：

- class 名称。
- function 名称。
- import 摘要。

Java：

- class/interface 名称。
- public method 名称。

TypeScript/JavaScript：

- export function。
- class。
- package scripts。

MVP 可以只支持 Python。

## 历史压缩策略

当历史超过限制时：

1. 保留用户原始任务。
2. 保留最近 10 轮完整 action/observation。
3. 将更早 observation 压缩成短摘要。
4. 永远保留 modified_files。
5. 永远保留 inspected_paths。
6. 永远保留 verification_records。
7. 永远保留最近一次错误。

Rolling Task Summary 由 runtime 生成，不额外调用 LLM。它包含：

- 已压缩步骤数量。
- 已查看路径。
- 已修改路径。
- 验证记录。
- 重要决定，例如 target_scope 和重要说明文件工作笔记。
- 近期错误。
- 下一步建议。

## 重复探索抑制

工具执行后会记录 inspected_paths：

- list_dir 记录被列出的目录。
- read_file 记录被读取的文件。
- search 记录搜索根路径。

每轮 prompt 都会把 inspected_paths 放进 Current state。模型应利用该列表避免重复查看同一路径，除非该路径刚被修改或上一次访问失败。

## 进展守卫

Agent Loop 会对探索行为做轻量约束：

- 探索工具包括 list_dir、read_file、search。
- 同一工具反复查看同一路径超过限制时，返回 RepeatedInspection。
- Build 模式连续探索超过预算时，返回 ExplorationBudgetExceeded。
- 这些 observation 会附带 retry_hint，要求模型停止探索，转向 write_file、replace_in_file、run_shell 或 finish。

这个机制用于处理模型“虽然每步都成功，但一直不推进任务”的情况。它不是替代模型推理，而是给 agent loop 增加最低限度的进展控制。

## 目标范围守卫

Target Scope Guard 负责在工具执行前检查路径是否偏离当前任务目标。

- 覆盖 list_dir、read_file、search、write_file、append_file、replace_in_file。
- 如果路径不在 target_scope 内，工具不会执行。
- 返回 TargetScopeViolation，并提示模型回到目标目录内继续行动。
- 如果用户在当前任务中明确写出了另一个路径，可允许该路径作为例外。
- 这个机制用于避免模型找到目标目录后，又跑去 src、tests 或其他 examples 中做无关探索。

## Observation 截断策略

工具返回过长时：

- 保留开头和结尾。
- 标记 truncated = true。
- 提示模型可用 read_file 读取更小范围。

## 输出预算与分块生成

上下文预算控制输入给模型的内容量，输出预算控制模型单次响应的生成量。

- LLM 调用通过 `AGENT_LLM_MAX_TOKENS` 限制单次输出 token。
- 生成较大代码文件时，模型每轮只生成当前 chunk，不在一次响应里输出完整文件。
- 第一个 chunk 使用 `write_file`，后续 chunk 使用 `append_file`。
- 每个 chunk 目标为 60-100 行；如果 JSON 解析失败或疑似响应过长，下一轮降到 40-80 行。
- 工具执行成功后返回本次写入行数，供下一轮继续生成。

## 取舍说明

不使用向量数据库：

- 当前项目目标是实现 coding agent 基础闭环。
- 向量检索会增加依赖和解释成本。
- 对小型演示项目，文件树、搜索和 repo map 已足够。

采用最近历史 + 摘要：

- 实现简单。
- 能体现上下文窗口意识。
- 易于在面试中解释。
