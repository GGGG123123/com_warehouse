# rag-agent - MilvusSearchLatencyHigh 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0148-milvus_search_slow-rag-agent`
- 数据类型: `aiops_incident_case`
- 告警名称: `MilvusSearchLatencyHigh`
- 告警分类: `向量数据库异常`
- 告警级别: `warning`
- 受影响服务: `rag-agent`
- 命名空间: `prod`
- 责任团队: `ai-team`

## 事件摘要

`rag-agent` 触发 `MilvusSearchLatencyHigh`，触发条件为：Milvus 向量检索 P95 延迟连续 10 分钟超过 1 秒。
用户侧表现为：知识检索变慢，RAG 回答等待时间增加，部分查询超时。

## 关键证据

### 指标证据

- 推荐查询: `histogram_quantile(0.95, sum(rate(milvus_proxy_search_latency_bucket[5m])) by (le))`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `search timeout OR querynode overloaded`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `MilvusSearchLatencyHigh` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：collection 未完全 load 或分片分布不均

## 处置过程

1. 确认 collection load 状态
2. 降低 top_k 或调整 nprobe 等搜索参数
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 查询超时错误消失
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
