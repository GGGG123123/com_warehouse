# order-service - EmbeddingAPIFailureRateHigh 运维处置知识

## 元数据

- 文档ID: `AIOPS-0253-embedding_api_failure-order-service`
- 数据类型: `aiops_runbook`
- 告警名称: `EmbeddingAPIFailureRateHigh`
- 告警分类: `AI 服务异常`
- 告警级别: `critical`
- 服务名称: `order-service`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `order-team`
- 日志主题: `application-logs`
- 指标 Job: `order-service`

## 触发条件

Embedding API 调用失败率连续 5 分钟超过 5%

## 症状描述

文档入库失败、RAG 检索缺失新知识、用户问题无法获得相关上下文。

## 推荐 PromQL

- `sum(rate(embedding_request_errors_total{service="$service"}[5m])) by (error_code)`
- `histogram_quantile(0.95, sum(rate(embedding_request_duration_seconds_bucket[5m])) by (le))`

## 推荐日志查询

- `embedding failed OR rate limit`
- `429 OR timeout OR invalid api key`

## 常见根因

- Embedding 服务限流或配额耗尽
- API Key 无效或权限变更
- 请求批量过大导致超时
- 网络代理或 DNS 异常

## 立即处置

1. 检查 API Key 和服务配额
2. 降低批量大小并启用重试退避
3. 暂停低优先级批量入库任务
4. 切换备用模型或备用账号

## 诊断步骤

1. 按错误码统计 embedding 调用失败
2. 查看请求耗时、批量大小和输入长度
3. 检查 embedding 服务状态和账号配额
4. 确认网络代理和 DNS 解析正常

## 验证标准

- embedding 调用成功率恢复到 99% 以上
- 文档入库任务恢复推进
- 无新的限流或鉴权错误

## 预防措施

- 增加配额水位告警
- 入库任务做限速和断点续传
- 对 embedding 失败记录建立重试队列

## Agent 使用提示

当用户询问 `order-service` 的 `EmbeddingAPIFailureRateHigh`、`AI 服务异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
