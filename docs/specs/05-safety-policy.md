# Safety Policy Spec

## 安全目标

本项目的 agent 会读写本地文件并执行命令，因此必须把 LLM 的建议动作和本地真实执行隔离开。LLM 只能提出 action，本地安全策略决定是否允许执行。

## Workspace 边界

所有路径在执行前必须：

1. 基于 workspace 解析为绝对路径。
2. resolve 规范化。
3. 检查结果是否仍位于 workspace 内。

如果路径越界，返回 PathDenied。

示例：

```text
workspace = D:\project
允许：D:\project\src\main.py
拒绝：D:\project\..\secret.txt
拒绝：C:\Users\name\.ssh\id_rsa
```

## 敏感文件策略

默认拒绝读取或写入：

- .env
- .env.*
- *.pem
- *.key
- id_rsa
- id_dsa
- id_ed25519
- credentials.json
- token.json
- *secret*
- *password*

如果用户明确要求处理配置样例，应使用 `.env.example`，不得写入真实 key。

## 命令执行策略

run_shell 必须满足：

- cwd 固定为 workspace。
- 默认 timeout 为 30 秒。
- stdout 和 stderr 分别截断。
- 返回 exit_code。
- 不允许后台长期运行进程作为默认行为。

## 默认拒绝命令

匹配以下模式时默认拒绝：

- `rm -rf`
- `del /s`
- `rmdir /s`
- `git reset --hard`
- `git clean -fd`
- `git push`
- `git push --force`
- `curl ... | sh`
- `wget ... | sh`
- `Invoke-Expression`
- `iex`
- `format`

## 高风险命令确认

以下命令可作为加分项设计为人工确认：

- 删除文件。
- 覆盖大文件。
- 安装依赖。
- 运行网络下载命令。
- 修改 git 历史。

MVP 可以先拒绝，不实现交互确认。

## 文件大小限制

建议默认限制：

- read_file 单次最多 120 行。
- 单个 observation 最多 8000 字符。
- write_file 写入前检查内容大小。
- search 最多返回 50 条匹配。

## 错误返回

安全策略拒绝时，不抛出未捕获异常，而是返回结构化 observation：

```json
{
  "ok": false,
  "error_type": "PolicyDenied",
  "message": "Command is blocked by safety policy."
}
```

## 面试说明口径

可以这样解释：

“我的 agent 中，模型没有直接文件系统和 shell 权限。模型只能输出 JSON action，本地 Tool Registry 和 Safety Policy 负责解析、校验和拒绝危险行为。这是为了把智能决策和系统权限隔离开。”
