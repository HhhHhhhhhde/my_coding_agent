# Skill System Spec

## 目标

Skill 机制用于把可复用的工作偏好沉淀为本地 `SKILL.md` 文件，并在交互模式中跨多个任务持续注入给 agent。它不是外部插件系统，也不提供额外权限；skill 只影响模型上下文，实际文件和 shell 操作仍经过原有工具协议与 safety policy。

## 文件结构

默认 skill 根目录是当前 workspace 下的 `skills/`：

```text
skills/
  python-testing/
    SKILL.md
  safety-review/
    SKILL.md
  compact-planner/
    SKILL.md
  demo-skill/
    SKILL.md
```

每个 skill 至少包含名称、描述和具体指令。用户可以手写文件，也可以在 build 模式中让 agent 创建新的 `skills/<name>/SKILL.md`。

## 交互命令

```text
/skills          列出当前 workspace 可用 skill
/skill           查看已启用 skill
/skill active    查看已启用 skill
/skill use NAME  启用 skill
/skill remove NAME
/skill clear
/skill new NAME
```

启用后的 skill 会保存在当前交互会话的 `SkillSession` 中，后续任务都会收到 active skill context，直到用户手动移除或清空。非交互命令不会自动继承上一次交互中的 skill。

## 注入方式

`CodingAgent.run()` 接收 `skill_context` 与 `active_skills`。构造 prompt 时会把 active skill 作为独立上下文段落注入，并在 trajectory `run_start` 中记录已启用 skill 名称，便于回放时确认当时的行为约束。

## 安全边界

1. Skill 不绕过 workspace 限制。
2. Skill 不绕过敏感文件保护。
3. Skill 不绕过 shell 风险控制和确认机制。
4. Skill 内容只作为模型指令，工具参数仍由本地 parser、registry 和 safety policy 校验。

## 演示验证

`demo-skill` 专门用于验证 skill 生效：数学函数任务中，`sin` 和 `cos` 应使用轻量泰勒多项式近似，而不是直接调用 `math.sin` 或 `math.cos` 作为函数本体。测试仍可与标准库结果对比。
