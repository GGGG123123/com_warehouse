# mysql-primary - DiskIOHigh 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0304-disk_io_high-mysql-primary`
- 数据类型: `aiops_incident_case`
- 告警名称: `DiskIOHigh`
- 告警分类: `存储异常`
- 告警级别: `warning`
- 受影响服务: `mysql-primary`
- 命名空间: `prod`
- 责任团队: `dba-team`

## 事件摘要

`mysql-primary` 触发 `DiskIOHigh`，触发条件为：磁盘 IO 使用率连续 10 分钟超过 80%。
用户侧表现为：读写延迟升高，数据库或日志写入变慢，应用响应抖动。

## 关键证据

### 指标证据

- 推荐查询: `rate(node_disk_io_time_seconds_total[5m])`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `i/o timeout OR disk io high OR fsync slow`
- 日志主题: `database-logs`
- 证据模式: 日志中出现与 `DiskIOHigh` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：数据库 checkpoint、WAL 或 compaction 压力

## 处置过程

1. 暂停低优先级导入、备份或压缩任务
2. 将日志写入和数据盘隔离
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 读写 await 恢复到基线
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
