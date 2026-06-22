# Ingress5xxRateHigh 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0320-ingress_5xx`
- 数据类型: `aiops_alert_rule`
- 告警名称: `Ingress5xxRateHigh`
- 告警分类: `网关异常`
- 默认级别: `critical`

## 告警语义

Ingress 5xx 比例连续 5 分钟超过 3%

## 适用场景

入口网关返回 502/503/504，用户无法访问服务或请求超时。

## 推荐 PromQL 模板

- `sum(rate(nginx_ingress_controller_requests{status=~"5.."}[5m])) by (ingress)`
- `sum(rate(nginx_ingress_controller_request_duration_seconds_count[5m])) by (ingress)`

## 推荐日志查询模板

- `status:502 OR status:503 OR status:504`
- `upstream timed out OR no live upstreams`

## 根因候选

- 后端 Pod 不健康或 endpoints 为空
- 上游服务响应超时
- Ingress 配置或路由规则错误
- 网关资源不足导致连接排队

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `Ingress5xxRateHigh`、`网关异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
