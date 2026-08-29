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
   - 默认 N = 6。

5. Long-term task summary
   - 更早步骤的压缩摘要。
   - 已修改文件。
   - 已查看路径。
   - 已运行命令。
   - 当前失败或阻塞点。

6. Target-focus hints
   - 如果用户任务明确指定目标路径，应优先围绕该路径行动。
   - 如果目标目录不存在，Build 模式应创建目标文件，不应反复查看无关示例。
   - 相似示例最多查看一个，用于确认风格后就进入目标实现。

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
2. 保留最近 6 轮完整 action/observation。
3. 将更早 observation 压缩成短摘要。
4. 永远保留 modified_files。
5. 永远保留 inspected_paths。
6. 永远保留 verification_records。
7. 永远保留最近一次错误。

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

## Observation 截断策略

工具返回过长时：

- 保留开头和结尾。
- 标记 truncated = true。
- 提示模型可用 read_file 读取更小范围。

## 取舍说明

不使用向量数据库：

- 当前项目目标是实现 coding agent 基础闭环。
- 向量检索会增加依赖和解释成本。
- 对小型演示项目，文件树、搜索和 repo map 已足够。

采用最近历史 + 摘要：

- 实现简单。
- 能体现上下文窗口意识。
- 易于在面试中解释。
