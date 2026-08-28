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
   - 已运行命令。
   - 当前失败或阻塞点。

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
5. 永远保留 verification_records。
6. 永远保留最近一次错误。

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
