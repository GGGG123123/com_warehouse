# payment-service - EmbeddingAPIFailureRateHigh 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0256-embedding_api_failure-payment-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `EmbeddingAPIFailureRateHigh`
- 告警分类: `AI 服务异常`
- 告警级别: `critical`
- 受影响服务: `payment-service`
- 命名空间: `prod`
- 责任团队: `payment-team`

## 事件摘要

`payment-service` 触发 `EmbeddingAPIFailureRateHigh`，触发条件为：Embedding API 调用失败率连续 5 分钟超过 5%。
用户侧表现为：文档入库失败、RAG 检索缺失新知识、用户问题无法获得相关上下文。

## 关键证据

### 指标证据

- 推荐查询: `sum(rate(embedding_request_errors_total{service="$service"}[5m])) by (error_code)`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `embedding failed OR rate limit`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `EmbeddingAPIFailureRateHigh` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：Embedding 服务限流或配额耗尽

## 处置过程

1. 检查 API Key 和服务配额
2. 降低批量大小并启用重试退避
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 文档入库任务恢复推进
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
