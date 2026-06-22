# user-service - HighCPUUsage 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0008-high_cpu-user-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `HighCPUUsage`
- 告警分类: `资源异常`
- 告警级别: `critical`
- 受影响服务: `user-service`
- 命名空间: `prod`
- 责任团队: `user-team`

## 事件摘要

`user-service` 触发 `HighCPUUsage`，触发条件为：CPU 使用率连续 5 分钟超过 85%。
用户侧表现为：实例负载升高、接口响应变慢、请求排队增加，严重时出现超时。

## 关键证据

### 指标证据

- 推荐查询: `avg(rate(container_cpu_usage_seconds_total{pod=~"$pod"}[5m])) by (pod)`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `level:ERROR OR cpu_usage:>85`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `HighCPUUsage` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：流量突增导致业务线程持续满载

## 处置过程

1. 确认是否单实例异常，必要时摘除异常实例
2. 如果整体流量上涨，优先水平扩容
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 错误率和超时数量不再增长
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
