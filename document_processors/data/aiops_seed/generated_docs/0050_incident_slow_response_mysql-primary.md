# mysql-primary - SlowResponse 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0050-slow_response-mysql-primary`
- 数据类型: `aiops_incident_case`
- 告警名称: `SlowResponse`
- 告警分类: `性能异常`
- 告警级别: `warning`
- 受影响服务: `mysql-primary`
- 命名空间: `prod`
- 责任团队: `dba-team`

## 事件摘要

`mysql-primary` 触发 `SlowResponse`，触发条件为：P99 响应时间连续 5 分钟超过 3 秒。
用户侧表现为：用户请求明显变慢，部分请求超时，下游调用耗时升高。

## 关键证据

### 指标证据

- 推荐查询: `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `response_time:>3000 OR timeout:true`
- 日志主题: `database-logs`
- 证据模式: 日志中出现与 `SlowResponse` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：缓存命中率下降导致数据库压力上升

## 处置过程

1. 对热点接口启用缓存或提高缓存 TTL
2. 对异常下游启用熔断和超时控制
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 核心链路成功率恢复正常
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
