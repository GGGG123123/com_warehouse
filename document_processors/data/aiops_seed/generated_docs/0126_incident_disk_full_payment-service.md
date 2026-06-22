# payment-service - DiskSpaceLow 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0126-disk_full-payment-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `DiskSpaceLow`
- 告警分类: `存储异常`
- 告警级别: `critical`
- 受影响服务: `payment-service`
- 命名空间: `prod`
- 责任团队: `payment-team`

## 事件摘要

`payment-service` 触发 `DiskSpaceLow`，触发条件为：磁盘使用率连续 10 分钟超过 90%。
用户侧表现为：日志无法写入、数据库写入失败、服务可能进入只读或崩溃。

## 关键证据

### 指标证据

- 推荐查询: `node_filesystem_avail_bytes{mountpoint="/"}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `No space left on device OR disk full`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `DiskSpaceLow` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：数据库 binlog、WAL 或 segment 文件增长

## 处置过程

1. 扩大磁盘或挂载新卷
2. 暂停产生大量文件的任务
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 磁盘使用率低于 75%
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
