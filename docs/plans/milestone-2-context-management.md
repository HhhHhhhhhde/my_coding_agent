# Milestone 2: Context Management

## 目标

让 agent 从单次任务工具循环，升级为具备连续会话感和上下文预算意识的本地 coding agent。

这一阶段不追求长期记忆系统，而是先解决交互模式下最真实的问题：用户连续提问时，agent 应该知道刚才发生了什么，同时不能让历史任务污染当前目标。

## 必做范围

1. Session State
   - 在 CLI 交互会话中维护最近任务记录。
   - 记录 task、mode、workspace、success、summary。
   - 记录 modified_files、verification_records、trajectory_path、output_path。

2. Session Context Injection
   - `CodingAgent.run()` 支持传入可选 session context。
   - `context.build_messages()` 将最近若干轮摘要加入 prompt。
   - 明确区分 Current Task 和 Recent Session Context。

3. Context Priority
   - 当前用户任务优先级高于历史上下文。
   - 当前 workspace 优先级高于上一轮 workspace。
   - 如果用户明确给出目标路径，历史任务不能改变目标路径。

4. Context Budget
   - 默认只注入最近 3 轮会话摘要。
   - 摘要只包含必要字段，不注入完整 trajectory。
   - 长 summary 需要截断或压缩。

5. Session Commands
   - `/clear` 清空会话上下文。
   - `/history` 查看当前会话摘要。
   - 可选：`/last` 查看上一轮任务结果。

6. Plan Output Awareness
   - plan 模式生成的 markdown 路径进入 session context。
   - 用户说“继续刚才的计划”时，agent 能看到上一轮 plan 文件位置。

## 验收标准

1. 连续交互中，用户说“继续刚才的任务”，agent 能引用上一轮 task、workspace 和修改文件。
2. 用户切换到新 workspace 后，agent 不会错误回到旧 workspace。
3. 用户执行 `/clear` 后，后续 prompt 中不再包含历史 session context。
4. trajectory 中能看到本轮是否使用了 session context。
5. session context 不包含 API key、`.env` 内容或完整敏感文件内容。

## 取舍原则

1. 会话上下文只保存摘要，不保存完整模型上下文。
2. 不在本阶段做向量检索或长期 memory。
3. 不让历史上下文覆盖当前任务。
4. 优先保证连续交互自然，而不是追求复杂记忆能力。

## 非目标

- 长期用户画像。
- 跨天持久化 memory。
- embedding 向量库。
- 自动总结整个仓库。
