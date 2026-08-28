# ADR-002: 使用自研 JSON Action 协议

## 状态

Accepted

## 背景

Agent 需要让 LLM 指挥本地工具。可选方案包括模型原生 tool calling 和自定义文本协议。

## 决策

MVP 使用自研 JSON action 协议。模型每轮输出一个 JSON object，包含 thought、action.tool 和 action.args。本地 Action Parser 负责解析和校验。

## 后果

优点：

- 实现简单。
- 易于测试。
- 模型厂商兼容性较好。
- 能体现自研模型输出解析逻辑。

代价：

- 需要处理模型输出非法 JSON。
- 参数 schema 校验需要自己写。
- 稳定性可能低于成熟 tool calling runtime。
