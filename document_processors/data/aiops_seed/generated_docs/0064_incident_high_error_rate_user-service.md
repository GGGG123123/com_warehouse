# user-service - HighErrorRate 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0064-high_error_rate-user-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `HighErrorRate`
- 告警分类: `业务错误`
- 告警级别: `critical`
- 受影响服务: `user-service`
- 命名空间: `prod`
- 责任团队: `user-team`

## 事件摘要

`user-service` 触发 `HighErrorRate`，触发条件为：5xx 错误率连续 5 分钟超过 5%。
用户侧表现为：接口返回 5xx 增多，用户操作失败，错误日志集中出现。

## 关键证据

### 指标证据

- 推荐查询: `sum(rate(http_requests_total{status=~"5..",service="$service"}[5m])) / sum(rate(http_requests_total{service="$service"}[5m]))`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `level:ERROR AND service:$service`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `HighErrorRate` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：新版本发布引入异常

## 处置过程

1. 确认是否和发布窗口重合，必要时回滚
2. 开启熔断降级，避免错误扩散
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 异常日志数量下降到基线
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
