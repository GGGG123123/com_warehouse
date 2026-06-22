# cls-collector - LogCollectorBacklogHigh 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0250-log_collector_backlog-cls-collector`
- 数据类型: `aiops_incident_case`
- 告警名称: `LogCollectorBacklogHigh`
- 告警分类: `日志采集异常`
- 告警级别: `warning`
- 受影响服务: `cls-collector`
- 命名空间: `prod`
- 责任团队: `sre-team`

## 事件摘要

`cls-collector` 触发 `LogCollectorBacklogHigh`，触发条件为：日志采集队列积压连续 10 分钟增长。
用户侧表现为：日志查询延迟，告警诊断缺少最新日志证据。

## 关键证据

### 指标证据

- 推荐查询: `collector_queue_size{job="$job"}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `collector backlog OR send failed OR retry`
- 日志主题: `collector-logs`
- 证据模式: 日志中出现与 `LogCollectorBacklogHigh` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：网络抖动导致发送失败重试

## 处置过程

1. 检查日志服务限流和配额
2. 优先保留 ERROR/WARN 关键日志
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 日志写入失败率归零
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
