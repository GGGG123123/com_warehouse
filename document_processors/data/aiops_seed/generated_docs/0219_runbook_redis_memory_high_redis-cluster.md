# redis-cluster - RedisMemoryHigh 运维处置知识

## 元数据

- 文档ID: `AIOPS-0219-redis_memory_high-redis-cluster`
- 数据类型: `aiops_runbook`
- 告警名称: `RedisMemoryHigh`
- 告警分类: `缓存异常`
- 告警级别: `warning`
- 服务名称: `redis-cluster`
- 服务角色: `cache`
- 命名空间: `prod`
- 责任团队: `platform-team`
- 日志主题: `redis-logs`
- 指标 Job: `redis`

## 触发条件

Redis 内存使用率连续 10 分钟超过 85%

## 症状描述

Redis 淘汰 key 增加，命中率波动，严重时写入失败。

## 推荐 PromQL

- `redis_memory_used_bytes / redis_memory_max_bytes`
- `rate(redis_evicted_keys_total[5m])`

## 推荐日志查询

- `OOM command not allowed OR evicted_keys`
- `redis memory high OR maxmemory`

## 常见根因

- 缓存 key 数量异常增长
- TTL 缺失导致冷数据长期驻留
- 大 value 写入 Redis
- maxmemory 配置小于业务峰值

## 立即处置

1. 清理异常大 key 或过期冷 key
2. 临时提高 Redis 容量或扩容分片
3. 限制大 value 写入
4. 调整淘汰策略保护核心 key

## 诊断步骤

1. 统计 key 前缀和大 key TopN
2. 查看 evicted_keys、used_memory、hit_rate
3. 确认最近是否有缓存结构变更
4. 检查 key TTL 分布

## 验证标准

- 内存使用率低于 70%
- evicted_keys 不再快速增长
- 缓存命中率恢复

## 预防措施

- 所有缓存 key 必须设置 TTL
- 定期扫描大 key 和热 key
- 新增缓存结构前进行容量评估

## Agent 使用提示

当用户询问 `redis-cluster` 的 `RedisMemoryHigh`、`缓存异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
