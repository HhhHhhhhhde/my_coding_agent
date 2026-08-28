# Demo Scenario Spec

## 视频目标

视频应在 2 分钟以内展示 agent 完成一个真实编程任务，并简要讲解核心实现。演示任务必须稳定、可重复，不依赖网络，不临场选择复杂项目。

## 推荐演示项目

创建一个小型 Python demo project：

```text
examples/demo_calculator/
  calculator.py
  test_calculator.py
```

初始状态包含一个明确 bug，例如：

```python
def add(a, b):
    return a - b
```

测试：

```python
def test_add():
    assert add(2, 3) == 5
```

## 演示任务

用户输入：

```text
请修复这个项目中的测试失败，并验证测试通过。
```

## 期望 Agent 行为

1. list_dir 查看项目结构。
2. read_file 读取测试文件。
3. run_shell 执行测试，得到失败信息。
4. read_file 读取源码。
5. replace_in_file 修复 bug。
6. run_shell 再次执行测试。
7. git_diff 查看修改。
8. finish 输出总结。

## 视频结构

1. 0-20 秒：说明项目目标和限制。
   - 自研 coding agent。
   - 不使用 agent 框架。
   - 本地工具由自己实现。

2. 20-90 秒：演示 agent 执行任务。
   - 展示命令行输入。
   - 展示 agent 多轮 action。
   - 展示测试失败到测试通过。

3. 90-115 秒：展示核心架构。
   - Agent Loop。
   - Tool Registry。
   - Safety Policy。
   - Trajectory Logger。

4. 115-120 秒：展示结果。
   - 修改文件。
   - 验证命令。
   - trajectory 日志。

## 可选更高级演示

如果 MVP 稳定后，可以改用稍复杂任务：

- 为一个函数补充边界条件。
- 添加一个新 CLI 参数并补测试。
- 修复 lint 或类型检查错误。

不建议视频中演示：

- 大型真实仓库。
- 网络安装依赖。
- 需要长时间运行的测试。
- 多文件复杂重构。

## README.txt 要点

README.txt 控制在 1000 汉字以内，必须包含：

- Git 仓库地址。
- 运行方式。
- API key 配置方式。
- 核心功能。
- 特色功能。
- 演示任务说明。

不要包含：

- 真实 API key。
- 过长架构说明。
- 与提交无关的开发日志。
