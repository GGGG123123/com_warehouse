# embedding-worker - KafkaConsumerLagHigh 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0100-queue_lag-embedding-worker`
- 数据类型: `aiops_incident_case`
- 告警名称: `KafkaConsumerLagHigh`
- 告警分类: `消息队列异常`
- 告警级别: `critical`
- 受影响服务: `embedding-worker`
- 命名空间: `prod`
- 责任团队: `ai-team`

## 事件摘要

`embedding-worker` 触发 `KafkaConsumerLagHigh`，触发条件为：消费者 lag 连续 10 分钟增长且超过 10000。
用户侧表现为：异步任务积压，业务状态更新延迟，用户看到数据不同步。

## 关键证据

### 指标证据

- 推荐查询: `kafka_consumergroup_lag{consumer_group="$group"}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `consumer lag OR rebalance OR poll timeout`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `KafkaConsumerLagHigh` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：消费端处理能力不足

## 处置过程

1. 扩容消费者实例或提高并发
2. 暂停异常消息并转入死信队列
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 死信队列无新增异常消息
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
