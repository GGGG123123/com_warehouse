# SlowResponse 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0311-slow_response`
- 数据类型: `aiops_alert_rule`
- 告警名称: `SlowResponse`
- 告警分类: `性能异常`
- 默认级别: `warning`

## 告警语义

P99 响应时间连续 5 分钟超过 3 秒

## 适用场景

用户请求明显变慢，部分请求超时，下游调用耗时升高。

## 推荐 PromQL 模板

- `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))`
- `sum(rate(http_requests_total{service="$service",status=~"5.."}[5m]))`

## 推荐日志查询模板

- `response_time:>3000 OR timeout:true`
- `slow_query:true OR upstream_timeout:true`

## 根因候选

- 数据库慢查询或缺少索引
- 下游接口响应慢或超时
- 缓存命中率下降导致数据库压力上升
- 线程池耗尽或连接池耗尽

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `SlowResponse`、`性能异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
