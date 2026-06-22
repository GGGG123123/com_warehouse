# rag-agent - MilvusSearchLatencyHigh 运维处置知识

## 元数据

- 文档ID: `AIOPS-0147-milvus_search_slow-rag-agent`
- 数据类型: `aiops_runbook`
- 告警名称: `MilvusSearchLatencyHigh`
- 告警分类: `向量数据库异常`
- 告警级别: `warning`
- 服务名称: `rag-agent`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `ai-team`
- 日志主题: `application-logs`
- 指标 Job: `rag-agent`

## 触发条件

Milvus 向量检索 P95 延迟连续 10 分钟超过 1 秒

## 症状描述

知识检索变慢，RAG 回答等待时间增加，部分查询超时。

## 推荐 PromQL

- `histogram_quantile(0.95, sum(rate(milvus_proxy_search_latency_bucket[5m])) by (le))`
- `sum(rate(milvus_querynode_search_total[5m])) by (status)`

## 推荐日志查询

- `search timeout OR querynode overloaded`
- `collection not loaded OR index not found`

## 常见根因

- collection 未完全 load 或分片分布不均
- 索引参数不合理导致召回代价高
- QueryNode 资源不足
- 批量导入和查询同时进行造成资源争用

## 立即处置

1. 确认 collection load 状态
2. 降低 top_k 或调整 nprobe 等搜索参数
3. 扩容 QueryNode 或隔离导入任务
4. 对低优先级查询做限流

## 诊断步骤

1. 检查 Milvus Proxy 和 QueryNode 日志
2. 查看 collection、segment、index 状态
3. 分析查询 top_k、过滤条件和并发量
4. 对比导入任务和搜索延迟时间线

## 验证标准

- 搜索 P95 延迟恢复到 500ms 以下
- 查询超时错误消失
- RAG 回答整体耗时恢复

## 预防措施

- 导入和查询错峰
- 为 collection 建立索引状态巡检
- 按业务使用场景调优 top_k 和搜索参数

## Agent 使用提示

当用户询问 `rag-agent` 的 `MilvusSearchLatencyHigh`、`向量数据库异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
