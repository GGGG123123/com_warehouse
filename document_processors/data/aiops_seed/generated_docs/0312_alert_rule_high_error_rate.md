# HighErrorRate 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0312-high_error_rate`
- 数据类型: `aiops_alert_rule`
- 告警名称: `HighErrorRate`
- 告警分类: `业务错误`
- 默认级别: `critical`

## 告警语义

5xx 错误率连续 5 分钟超过 5%

## 适用场景

接口返回 5xx 增多，用户操作失败，错误日志集中出现。

## 推荐 PromQL 模板

- `sum(rate(http_requests_total{status=~"5..",service="$service"}[5m])) / sum(rate(http_requests_total{service="$service"}[5m]))`
- `sum(rate(exceptions_total{service="$service"}[5m])) by (exception)`

## 推荐日志查询模板

- `level:ERROR AND service:$service`
- `exception OR stacktrace OR panic OR traceback`

## 根因候选

- 新版本发布引入异常
- 配置错误导致依赖地址或密钥不可用
- 下游服务失败未做降级
- 数据库或缓存连接异常

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `HighErrorRate`、`业务错误`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
