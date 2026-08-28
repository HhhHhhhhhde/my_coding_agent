# ADR-001: 不使用现成 Agent 框架

## 状态

Accepted

## 背景

题目明确要求不得使用 LangChain、LlamaIndex、OpenAI Agents SDK、Claude Agent SDK、AutoGen、CrewAI 等 agent 框架，也不得封装现成 agent 产品。

## 决策

项目只使用普通模型 API 客户端或 HTTP 请求调用 LLM。Agent Loop、工具协议、工具执行、上下文管理、错误处理和终止条件全部自行实现。

## 后果

优点：

- 符合题目要求。
- 每个核心模块都可以在面试中解释。
- 便于展示 agent 的真实运行机制。

代价：

- 需要自行处理解析失败、工具异常和上下文长度。
- 开发速度慢于直接使用框架。
