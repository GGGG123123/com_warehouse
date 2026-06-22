# redis-cluster - RedisMemoryHigh 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0220-redis_memory_high-redis-cluster`
- 数据类型: `aiops_incident_case`
- 告警名称: `RedisMemoryHigh`
- 告警分类: `缓存异常`
- 告警级别: `warning`
- 受影响服务: `redis-cluster`
- 命名空间: `prod`
- 责任团队: `platform-team`

## 事件摘要

`redis-cluster` 触发 `RedisMemoryHigh`，触发条件为：Redis 内存使用率连续 10 分钟超过 85%。
用户侧表现为：Redis 淘汰 key 增加，命中率波动，严重时写入失败。

## 关键证据

### 指标证据

- 推荐查询: `redis_memory_used_bytes / redis_memory_max_bytes`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `OOM command not allowed OR evicted_keys`
- 日志主题: `redis-logs`
- 证据模式: 日志中出现与 `RedisMemoryHigh` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：缓存 key 数量异常增长

## 处置过程

1. 清理异常大 key 或过期冷 key
2. 临时提高 Redis 容量或扩容分片
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- evicted_keys 不再快速增长
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
