# MilvusSearchLatencyHigh 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0318-milvus_search_slow`
- 数据类型: `aiops_alert_rule`
- 告警名称: `MilvusSearchLatencyHigh`
- 告警分类: `向量数据库异常`
- 默认级别: `warning`

## 告警语义

Milvus 向量检索 P95 延迟连续 10 分钟超过 1 秒

## 适用场景

知识检索变慢，RAG 回答等待时间增加，部分查询超时。

## 推荐 PromQL 模板

- `histogram_quantile(0.95, sum(rate(milvus_proxy_search_latency_bucket[5m])) by (le))`
- `sum(rate(milvus_querynode_search_total[5m])) by (status)`

## 推荐日志查询模板

- `search timeout OR querynode overloaded`
- `collection not loaded OR index not found`

## 根因候选

- collection 未完全 load 或分片分布不均
- 索引参数不合理导致召回代价高
- QueryNode 资源不足
- 批量导入和查询同时进行造成资源争用

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `MilvusSearchLatencyHigh`、`向量数据库异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
