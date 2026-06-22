# payment-service - Ingress5xxRateHigh 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0168-ingress_5xx-payment-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `Ingress5xxRateHigh`
- 告警分类: `网关异常`
- 告警级别: `critical`
- 受影响服务: `payment-service`
- 命名空间: `prod`
- 责任团队: `payment-team`

## 事件摘要

`payment-service` 触发 `Ingress5xxRateHigh`，触发条件为：Ingress 5xx 比例连续 5 分钟超过 3%。
用户侧表现为：入口网关返回 502/503/504，用户无法访问服务或请求超时。

## 关键证据

### 指标证据

- 推荐查询: `sum(rate(nginx_ingress_controller_requests{status=~"5.."}[5m])) by (ingress)`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `status:502 OR status:503 OR status:504`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `Ingress5xxRateHigh` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：后端 Pod 不健康或 endpoints 为空

## 处置过程

1. 确认后端服务 endpoints 是否存在
2. 回滚最近的 Ingress 配置变更
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 5xx 比例恢复到 0.5% 以下
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
