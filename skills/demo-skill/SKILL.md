---
name: demo-skill
description: 为数学函数任务演示 skill 生效：使用轻量多项式近似实现三角函数，不引入第三方依赖。
---

# demo-skill

## When To Use
- 当任务要求实现或编写数学函数（如 sin、cos、ln、abs、exp、sqrt 等）时。
- 当代码中包含数学计算、数值计算或函数测试相关需求时。

## Instructions
1. 遇到 `sin` 或 `cos` ，`ln`实现时，使用内置的泰勒多项式近似，不直接调用 `math.sin` 或 `math.cos` ，`math.log`作为函数本体。
2. 不要引入 numpy、scipy 或其他新依赖；多项式系数直接写在代码里即可。
3. 可以使用 `math.pi`、取模和基础算术做角度归一化；这不算调用精确三角函数。
4. 对 `abs` 使用内置 `abs`，保持实现简洁。
5. 新建示例文件时保持结构小而清楚，优先创建一个实现文件和一个对应测试文件。
6. 测试允许与标准库 `math.sin`、`math.cos`、`math.log` 对比，使用合理误差，例如 `1e-4` 或 `1e-5`。
7. 修改或新增数学函数后，运行最小相关测试验证结果。
