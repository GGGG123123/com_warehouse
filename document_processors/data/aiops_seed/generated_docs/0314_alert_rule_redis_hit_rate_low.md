# RedisHitRateLow 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0314-redis_hit_rate_low`
- 数据类型: `aiops_alert_rule`
- 告警名称: `RedisHitRateLow`
- 告警分类: `缓存异常`
- 默认级别: `warning`

## 告警语义

Redis 命中率连续 10 分钟低于 80%

## 适用场景

数据库查询量上升，接口延迟增加，缓存 miss 日志增多。

## 推荐 PromQL 模板

- `redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)`
- `rate(redis_commands_processed_total[5m])`

## 推荐日志查询模板

- `cache_miss:true OR cache_penetration:true`
- `redis timeout OR redis connection refused`

## 根因候选

- 缓存批量过期导致击穿
- 缓存 key 设计不合理或版本变化
- 热点数据未预热
- 恶意或异常参数造成缓存穿透

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `RedisHitRateLow`、`缓存异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
