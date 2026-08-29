# Milestone 3: Reliability And Safety

## 目标

让 agent 从“能执行任务”升级为“失败后能恢复，并且不会静默执行高风险操作”。

这一阶段聚焦错误治理、重试策略和权限控制，是本项目从 demo 工具走向可靠 runtime 的关键阶段。

## 必做范围

1. Error Taxonomy
   - ParserError：模型输出格式错误。
   - ToolError：工具参数错误、路径错误、替换失败。
   - LLMError：模型 API 调用失败。
   - VerificationError：测试或构建失败。
   - PermissionError：越权路径、敏感文件或高风险命令。
   - ProgressError：重复探索、重复失败、无效循环。

2. Retry Policy
   - 不同错误类型对应不同 retry hint。
   - ParserError 优先提示重新输出合法 JSON。
   - 写文件 JSON 失败时提示使用 `content_base64`。
   - ReplacementNotUnique 时提示先 read_file 再缩小替换范围。
   - 测试失败时提示读取失败栈和相关源码。
   - 连续同类错误达到阈值后停止。

3. Progress Guard Upgrade
   - 检测重复读取同一文件。
   - 检测重复搜索同一 pattern。
   - 检测过长探索链路。
   - 检测连续无修改、无验证、无 finish 的循环。

4. Permission Control
   - workspace 越界拒绝。
   - 默认拒绝读取 `.env`、key、token、credential 文件。
   - 覆盖已有文件前返回确认需求。
   - 删除文件、批量写入、安装依赖等操作进入高风险流程。

5. Shell Risk Control
   - 命令风险分级：safe、review、blocked。
   - safe：测试、格式化、只读检查。
   - review：安装依赖、生成大量文件、网络访问。
   - blocked：删除目录、修改 git 历史、读取敏感文件。

6. User Confirmation Protocol
   - 工具返回 `needs_confirmation` observation。
   - CLI 展示风险说明和待执行动作。
   - 用户确认后才继续执行。
   - 用户拒绝后将拒绝信息反馈给模型。

## 验收标准

1. agent 不能读写 workspace 外路径。
2. agent 不能直接读取 `.env`。
3. 高风险 shell 命令不会静默执行。
4. 重复格式错误不会无限循环。
5. 替换失败时能给出可执行的 retry hint。
6. 测试失败后 agent 会读取失败信息并尝试修复，而不是直接 finish。

## 取舍原则

1. 安全边界优先于任务完成率。
2. 拒绝原因必须可见、可记录、可解释。
3. 确认机制优先覆盖高风险操作，不阻塞普通读文件和测试命令。
4. retry policy 要简单明确，避免把 prompt 变成规则泥潭。

## 非目标

- 完整沙箱隔离。
- 操作系统级权限管理。
- 企业级审计系统。
- 自动联网安装依赖。
