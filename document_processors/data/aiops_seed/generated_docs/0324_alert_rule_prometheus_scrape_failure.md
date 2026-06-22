# PrometheusScrapeFailure 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0324-prometheus_scrape_failure`
- 数据类型: `aiops_alert_rule`
- 告警名称: `PrometheusScrapeFailure`
- 告警分类: `监控异常`
- 默认级别: `warning`

## 告警语义

Prometheus target scrape 失败率连续 10 分钟超过 20%

## 适用场景

指标缺失，告警可能失真，监控看板出现断点。

## 推荐 PromQL 模板

- `up{job="$job"} == 0`
- `sum(rate(prometheus_target_scrapes_exceeded_sample_limit_total[5m])) by (job)`

## 推荐日志查询模板

- `scrape failed OR context deadline exceeded`
- `sample limit exceeded OR target down`

## 根因候选

- 服务 metrics endpoint 不可达
- 采集超时或样本量过大
- 网络策略或安全组阻断
- Prometheus 负载过高

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `PrometheusScrapeFailure`、`监控异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
