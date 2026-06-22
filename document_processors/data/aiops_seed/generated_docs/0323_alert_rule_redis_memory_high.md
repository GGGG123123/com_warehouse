# RedisMemoryHigh 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0323-redis_memory_high`
- 数据类型: `aiops_alert_rule`
- 告警名称: `RedisMemoryHigh`
- 告警分类: `缓存异常`
- 默认级别: `warning`

## 告警语义

Redis 内存使用率连续 10 分钟超过 85%

## 适用场景

Redis 淘汰 key 增加，命中率波动，严重时写入失败。

## 推荐 PromQL 模板

- `redis_memory_used_bytes / redis_memory_max_bytes`
- `rate(redis_evicted_keys_total[5m])`

## 推荐日志查询模板

- `OOM command not allowed OR evicted_keys`
- `redis memory high OR maxmemory`

## 根因候选

- 缓存 key 数量异常增长
- TTL 缺失导致冷数据长期驻留
- 大 value 写入 Redis
- maxmemory 配置小于业务峰值

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `RedisMemoryHigh`、`缓存异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
