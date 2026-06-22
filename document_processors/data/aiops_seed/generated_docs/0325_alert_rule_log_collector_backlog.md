# LogCollectorBacklogHigh 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0325-log_collector_backlog`
- 数据类型: `aiops_alert_rule`
- 告警名称: `LogCollectorBacklogHigh`
- 告警分类: `日志采集异常`
- 默认级别: `warning`

## 告警语义

日志采集队列积压连续 10 分钟增长

## 适用场景

日志查询延迟，告警诊断缺少最新日志证据。

## 推荐 PromQL 模板

- `collector_queue_size{job="$job"}`
- `rate(collector_dropped_logs_total{job="$job"}[5m])`

## 推荐日志查询模板

- `collector backlog OR send failed OR retry`
- `rate limit exceeded OR log dropped`

## 根因候选

- 日志量突增超过采集吞吐
- 日志服务写入限流
- 网络抖动导致发送失败重试
- 采集 Agent 资源不足

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `LogCollectorBacklogHigh`、`日志采集异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
