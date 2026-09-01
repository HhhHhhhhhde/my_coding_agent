# Milestone 5: Lightweight Skills

## 状态

已完成首版。

## 目标

让用户可以把项目内可复用的工作方法写成 `SKILL.md`，并在交互模式中启用、查看和移除。启用后的 skill 在同一个交互会话内跨多轮任务持续生效。

## 已完成范围

1. Workspace Skill Discovery
   - 默认扫描 `skills/<name>/SKILL.md`。
   - `/skills` 可列出可用 skill。

2. Active Skill Session
   - `/skill use NAME` 启用 skill。
   - `/skill` 和 `/skill active` 查看当前已启用 skill。
   - `/skill remove NAME` 和 `/skill clear` 手动移除。

3. Agent Context Injection
   - `CodingAgent.run()` 支持 skill context。
   - prompt 中明确列出 active skills。
   - trajectory 记录 active skill 名称。

4. Agent-authored Skills
   - prompt 明确允许用户让 agent 创建新的 `skills/<name>/SKILL.md`。
   - `/skill new NAME` 可创建本地模板。

5. Demo Skills
   - `python-testing`
   - `safety-review`
   - `compact-planner`
   - `demo-skill`

## 验收标准

1. 用户可以列出 workspace 下的 skill。
2. 用户可以启用、查看、移除 skill。
3. 启用的 skill 会影响后续任务。
4. 多轮交互中 skill 会保持，直到用户清除。
5. 用户可以新增 skill 文件，并在后续任务启用。

## 非目标

- 不提供远程 skill marketplace。
- 不自动安装第三方依赖。
- 不让 skill 扩展工具权限。
- 不让 skill 绕过安全策略。
