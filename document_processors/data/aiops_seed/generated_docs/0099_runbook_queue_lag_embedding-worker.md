# embedding-worker - KafkaConsumerLagHigh 运维处置知识

## 元数据

- 文档ID: `AIOPS-0099-queue_lag-embedding-worker`
- 数据类型: `aiops_runbook`
- 告警名称: `KafkaConsumerLagHigh`
- 告警分类: `消息队列异常`
- 告警级别: `critical`
- 服务名称: `embedding-worker`
- 服务角色: `worker`
- 命名空间: `prod`
- 责任团队: `ai-team`
- 日志主题: `application-logs`
- 指标 Job: `embedding-worker`

## 触发条件

消费者 lag 连续 10 分钟增长且超过 10000

## 症状描述

异步任务积压，业务状态更新延迟，用户看到数据不同步。

## 推荐 PromQL

- `kafka_consumergroup_lag{consumer_group="$group"}`
- `sum(rate(kafka_topic_partition_current_offset[5m])) by (topic)`

## 推荐日志查询

- `consumer lag OR rebalance OR poll timeout`
- `message_process_error OR retry_exhausted`

## 常见根因

- 消费端处理能力不足
- 消息处理失败后反复重试
- 消费者频繁 rebalance
- 单分区热点导致并行度不足

## 立即处置

1. 扩容消费者实例或提高并发
2. 暂停异常消息并转入死信队列
3. 临时提高批量消费大小
4. 检查下游依赖，避免消费者阻塞

## 诊断步骤

1. 查看 lag 增长速度和 topic 分区分布
2. 查询消费失败日志和重试次数
3. 检查消费者实例是否频繁重启
4. 确认下游数据库或外部 API 是否变慢

## 验证标准

- consumer lag 持续下降
- 死信队列无新增异常消息
- 业务异步状态延迟恢复正常

## 预防措施

- 为消费者配置死信队列和限次重试
- 按 topic 分区评估并行度
- 对耗时任务拆分或异步化

## Agent 使用提示

当用户询问 `embedding-worker` 的 `KafkaConsumerLagHigh`、`消息队列异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
