# order-service - RedisHitRateLow 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0088-redis_hit_rate_low-order-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `RedisHitRateLow`
- 告警分类: `缓存异常`
- 告警级别: `warning`
- 受影响服务: `order-service`
- 命名空间: `prod`
- 责任团队: `order-team`

## 事件摘要

`order-service` 触发 `RedisHitRateLow`，触发条件为：Redis 命中率连续 10 分钟低于 80%。
用户侧表现为：数据库查询量上升，接口延迟增加，缓存 miss 日志增多。

## 关键证据

### 指标证据

- 推荐查询: `redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `cache_miss:true OR cache_penetration:true`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `RedisHitRateLow` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：缓存批量过期导致击穿

## 处置过程

1. 预热热点 key 并延长 TTL
2. 对空值结果设置短 TTL 缓存
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 数据库 QPS 回落到正常水平
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
