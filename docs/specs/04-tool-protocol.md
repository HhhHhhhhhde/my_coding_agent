# Tool Protocol Spec

## 协议目标

模型不能直接操作本地系统。模型必须输出结构化 JSON action，本地 agent 解析、校验并执行。这样可以把推理能力和执行权限分开。

## 模型输出格式

模型每一轮只能输出一个 JSON object，不输出 Markdown，不输出额外解释。

```json
{
  "thought": "I need to inspect the repository structure first.",
  "action": {
    "tool": "list_dir",
    "args": {
      "path": "."
    }
  }
}
```

## Action 字段

| 字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|
| thought | string | 是 | 简短说明本轮为什么选择这个动作 |
| action | object | 是 | 工具调用 |
| action.tool | string | 是 | 工具名 |
| action.args | object | 是 | 工具参数 |

## 工具列表

### list_dir

用途：查看目录。

参数：

```json
{
  "path": "."
}
```

### read_file

用途：按行读取文件。

参数：

```json
{
  "path": "src/main.py",
  "start": 1,
  "end": 120
}
```

### search

用途：搜索代码或文本。

参数：

```json
{
  "pattern": "def solve",
  "path": "."
}
```

### write_file

用途：创建或覆盖文件。

参数：

```json
{
  "path": "src/new_file.py",
  "content": "..."
}
```

### replace_in_file

用途：精确替换文件内容。

参数：

```json
{
  "path": "src/main.py",
  "old": "return a - b",
  "new": "return a + b"
}
```

约束：

- old 必须在文件中唯一出现。
- 如果出现 0 次或多次，工具返回错误。

### run_shell

用途：执行测试、构建或脚本。

参数：

```json
{
  "command": "pytest -q"
}
```

### git_diff

用途：查看当前修改。

参数：

```json
{}
```

### finish

用途：结束任务。

参数：

```json
{
  "summary": "Fixed the failing calculator test.",
  "changed_files": ["calculator.py"],
  "verification": "pytest -q passed"
}
```

## Observation 格式

成功：

```json
{
  "ok": true,
  "tool": "read_file",
  "content": "1: def add(a, b):\n2:     return a + b",
  "truncated": false
}
```

失败：

```json
{
  "ok": false,
  "tool": "read_file",
  "error_type": "PathDenied",
  "message": "Path is outside workspace"
}
```

## 解析失败处理

如果模型输出不是合法 JSON，agent 不执行任何本地动作，而是向模型反馈：

```json
{
  "ok": false,
  "tool": "parser",
  "error_type": "InvalidJson",
  "message": "Your response must be a single JSON object with action.tool and action.args."
}
```

## 协议取舍

选择自研 JSON action 的原因：

1. 易于解释和测试。
2. 不依赖 agent 框架。
3. 本地可以完全控制工具执行。
4. 失败时可以把解析错误反馈给模型。
5. 适合面试展示 agent 内部循环。

暂不使用原生 tool calling 的原因：

1. 原生 tool calling 虽被允许，但会弱化自研 action parser 的展示。
2. 不同模型厂商兼容性不同。
3. 自定义 JSON 更容易切换 OpenAI 兼容模型。
