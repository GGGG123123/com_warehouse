# api-gateway - HighMemoryUsage 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0022-high_memory-api-gateway`
- 数据类型: `aiops_incident_case`
- 告警名称: `HighMemoryUsage`
- 告警分类: `资源异常`
- 告警级别: `critical`
- 受影响服务: `api-gateway`
- 命名空间: `prod`
- 责任团队: `platform-team`

## 事件摘要

`api-gateway` 触发 `HighMemoryUsage`，触发条件为：内存使用率连续 5 分钟超过 85%。
用户侧表现为：内存持续上涨、GC 频繁、实例重启、可能触发 OOMKilled。

## 关键证据

### 指标证据

- 推荐查询: `container_memory_working_set_bytes{pod=~"$pod"}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `OutOfMemoryError OR OOMKilled OR memory_usage:>85`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `HighMemoryUsage` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：批处理任务一次性加载大对象

## 处置过程

1. 降低缓存容量或临时清理热点缓存
2. 暂停大批量导入或离线任务
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- Full GC 频率恢复正常
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
