# Milestone 1: MVP Agent Loop

## 目标

实现一个可以完成小型真实编程任务的最小可用 coding agent。

## 必做范围

1. CLI
   - 支持输入用户任务。
   - 支持 workspace、model、max_steps。
   - 从环境变量读取 API key。

2. LLM Client
   - 支持 OpenAI 兼容接口。
   - 能返回模型文本。
   - 能处理调用失败。

3. Agent Loop
   - 支持多轮 action / observation。
   - 支持 max_steps。
   - 支持 finish 终止。
   - 支持连续错误终止。

4. Action Parser
   - 解析 JSON action。
   - 校验 tool 和 args。
   - 解析失败反馈给模型。

5. Tools
   - list_dir。
   - read_file。
   - search。
   - write_file。
   - replace_in_file。
   - run_shell。
   - finish。

6. Basic runtime boundaries
   - 文件工具以 workspace 作为相对路径基准。
   - 命令在 workspace 内执行。
   - 命令超时。
   - 输出截断。

7. Logger
   - 记录 JSONL 轨迹。
   - 记录终止原因。

8. Demo
   - examples/demo_calculator。
   - 一个失败测试。
   - agent 能修复并运行测试通过。

9. Lightweight Plan / Build
   - Build 模式允许完整工具链。
   - Plan 模式只允许读取、搜索和 finish。
   - CLI 支持模式选择和连续交互。

## 验收标准

1. agent 能完成 demo_calculator 修复任务。
2. 运行结束后能看到修改文件和验证结果。
3. trajectory 日志包含每轮 action 和 observation。
4. 不依赖任何 agent 框架。
5. API key 不出现在仓库中。
6. Plan 模式不会修改文件。
7. 连续交互模式可以在一轮任务结束后继续执行下一轮。
