# Milestone 2: Context Management

## 目标

让 agent 从单次任务工具循环，升级为具备连续会话感和上下文预算意识的本地 coding agent。

这一阶段不追求长期记忆系统，而是先解决交互模式下最真实的问题：用户连续提问时，agent 应该知道刚才发生了什么，同时不能让历史任务污染当前目标。

## 必做范围

1. Session State
   - 在 CLI 交互会话中维护最近任务记录。
   - 记录 task、mode、workspace、success、summary。
   - 记录 modified_files、verification_records、trajectory_path、output_path。
   - 每轮任务结束后生成一段连续中文 turn summary。
   - turn summary 优先由 LLM 根据任务结果生成，失败时使用 runtime 兜底摘要。

2. Session Context Injection
   - `CodingAgent.run()` 支持传入可选 session context。
   - `context.build_messages()` 将最近若干轮摘要加入 prompt。
   - 明确区分 Current Task 和 Recent Session Context。
   - 最近会话摘要只作为背景信息，不能覆盖当前任务。
   - trajectory 的 start 事件记录本轮是否注入 session context。
   - 超出 recent history 的旧步骤会进入 Rolling Task Summary，而不是直接丢弃。

3. Context Priority
   - 当前用户任务优先级高于历史上下文。
   - 当前 workspace 优先级高于上一轮 workspace。
   - 如果用户明确给出目标路径，历史任务不能改变目标路径。
   - 如果本轮发现明确目标目录，后续路径工具必须优先留在该目录内。

4. Context Budget
   - 默认只注入最近 5 轮会话摘要。
   - 单轮 agent loop 默认保留最近 10 步 action/observation。
   - 更早步骤压缩为结构化 rolling summary，包含已查看、已修改、验证记录、重要决定、近期错误和下一步建议。
   - 摘要只包含必要字段，不注入完整 trajectory。
   - 长 summary 需要截断或压缩。
   - 注入 prompt 前对 API key、token、secret 等常见敏感模式做基础脱敏。
   - 对 README、GAMEPLAY、DESIGN、REQUIREMENTS、SPEC 等重要说明文件生成持久工作笔记，避免需求内容被 recent history 滚动挤出。
   - 生成大文件时，模型必须按 chunk 逐轮生成，不能在一次响应中输出完整长文件。
   - 单次 write_file/append_file 限制为 100 行，超过后要求改成 40-80 行小块重试。
   - LLM API 调用设置可配置的最大输出 token，避免长代码生成导致 CLI 长时间等待。
   - OpenAI-compatible 网关返回空内容时，在 LLM Client 内部重试并记录诊断信息。
   - 如果 reasoning_tokens 耗尽输出预算，空响应重试需要临时提高 max_tokens，并追加短 JSON action 恢复提示。

5. Session Commands
   - `/clear` 清空会话上下文。
   - `/history` 查看当前会话摘要。
   - `/summary` 或 `/last` 查看上一轮任务结果。
   - `/mode build` 和 `/mode plan` 切换模式。
   - `/workspace PATH` 切换工作区。
   - `/maxsteps N` 修改最大步数。
   - `/help` 查看命令列表。

6. Plan Output Awareness
   - plan 模式生成的 markdown 路径进入 session context。
   - 用户说“继续刚才的计划”时，agent 能看到上一轮 plan 文件位置。

7. Step Summary
   - 每个工具步骤在 CLI 中输出一段中文摘要。
   - 摘要说明本步调用了什么工具、目标是什么、执行是否成功。
   - step summary 由 runtime 生成，不额外消耗模型调用。

8. Turn Summary Event
   - 每轮任务结束后将最终 turn summary 追加到 trajectory。
   - turn summary 用于 CLI 展示、`/summary` 查看和下一轮 session context。

9. Target Scope Guard
   - 用户任务明确给出路径时，启动时锁定目标路径。
   - 读到或列出 README、GAMEPLAY、DESIGN、REQUIREMENTS、SPEC 等说明文件时，锁定其所在目录。
   - target_scope 写入 Current state。
   - target_scope 生效后，路径类工具访问目录外路径会返回 TargetScopeViolation。
   - CLI step summary 需要明确说明该访问被目标范围守卫拦截。

## 验收标准

1. 连续交互中，用户说“继续刚才的任务”，agent 能引用上一轮 task、workspace 和修改文件。
2. 用户切换到新 workspace 后，agent 不会错误回到旧 workspace。
3. 用户执行 `/clear` 后，后续 prompt 中不再包含历史 session context。
4. trajectory 中能看到本轮是否使用了 session context。
5. session context 不包含 API key、`.env` 内容或完整敏感文件内容。
6. 每轮任务结束后，CLI 输出由 LLM 生成的连续中文 turn summary。
7. `/summary` 可以查看上一轮中文总结，`/clear` 可以清空上下文。
8. 读取目标说明文件后，agent 不会继续探索 `src`、`tests` 或 sibling examples，除非用户明确要求。
9. 单轮超过 10 步后，prompt 中不再包含完整旧 observation，但能通过 Rolling Task Summary 看到较早步骤的关键事实。

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
