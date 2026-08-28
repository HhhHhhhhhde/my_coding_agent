# Milestone 2: Quality And Bonus Plan

## 目标

在 MVP 稳定后增加可解释性、安全性和演示效果，形成面试加分点。

## 加分功能

1. Plan / Build 双模式
   - Plan 模式禁用写文件和命令执行。
   - Build 模式允许完整工具集。
   - CLI 增加 `--mode plan|build`。

2. git_diff 工具
   - 展示当前修改。
   - finish 总结前建议调用。
   - 非 git 仓库返回明确提示。

3. 验证门禁
   - finish 前检查是否运行过测试或构建命令。
   - 如果没有验证，要求模型继续验证或说明无法验证原因。

4. 轻量 Repo Map
   - 启动时生成项目摘要。
   - MVP 后优先支持 Python class/function。
   - 将 repo map 放入初始上下文。

5. apply_patch
   - 支持补丁式编辑。
   - patch 失败时返回明确错误。
   - 保留 replace_in_file 作为简单可靠路径。

6. 轨迹回放
   - 将 JSONL 转成可读文本。
   - 包含步骤、工具、结果、错误和最终总结。

## 验收标准

1. Plan 模式不会修改文件。
2. Build 模式可以完成 demo。
3. finish 总结包含 changed_files 和 verification。
4. git_diff 能展示修改内容。
5. 轨迹回放可以用于视频展示。

## 取舍原则

1. 任何加分功能不得破坏 MVP 稳定性。
2. 视频演示优先选择最稳定路径。
3. 如果时间不足，优先保留 Plan / Build、验证门禁和轨迹日志。
