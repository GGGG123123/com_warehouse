# KafkaConsumerLagHigh 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0315-queue_lag`
- 数据类型: `aiops_alert_rule`
- 告警名称: `KafkaConsumerLagHigh`
- 告警分类: `消息队列异常`
- 默认级别: `critical`

## 告警语义

消费者 lag 连续 10 分钟增长且超过 10000

## 适用场景

异步任务积压，业务状态更新延迟，用户看到数据不同步。

## 推荐 PromQL 模板

- `kafka_consumergroup_lag{consumer_group="$group"}`
- `sum(rate(kafka_topic_partition_current_offset[5m])) by (topic)`

## 推荐日志查询模板

- `consumer lag OR rebalance OR poll timeout`
- `message_process_error OR retry_exhausted`

## 根因候选

- 消费端处理能力不足
- 消息处理失败后反复重试
- 消费者频繁 rebalance
- 单分区热点导致并行度不足

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `KafkaConsumerLagHigh`、`消息队列异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
