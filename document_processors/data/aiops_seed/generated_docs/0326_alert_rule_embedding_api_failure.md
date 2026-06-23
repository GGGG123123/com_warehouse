# EmbeddingAPIFailureRateHigh 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0326-embedding_api_failure`
- 数据类型: `aiops_alert_rule`
- 告警名称: `EmbeddingAPIFailureRateHigh`
- 告警分类: `AI 服务异常`
- 默认级别: `critical`

## 告警语义

Embedding API 调用失败率连续 5 分钟超过 5%

## 适用场景

文档入库失败、RAG 检索缺失新知识、用户问题无法获得相关上下文。

## 推荐 PromQL 模板

- `sum(rate(embedding_request_errors_total{service="$service"}[5m])) by (error_code)`
- `histogram_quantile(0.95, sum(rate(embedding_request_duration_seconds_bucket[5m])) by (le))`

## 推荐日志查询模板

- `embedding failed OR rate limit`
- `429 OR timeout OR invalid api key`

## 根因候选

- Embedding 服务限流或配额耗尽
- API Key 无效或权限变更
- 请求批量过大导致超时
- 网络代理或 DNS 异常

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `EmbeddingAPIFailureRateHigh`、`AI 服务异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
