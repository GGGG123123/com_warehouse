# rag-agent - RedisHitRateLow 运维处置知识

## 元数据

- 文档ID: `AIOPS-0093-redis_hit_rate_low-rag-agent`
- 数据类型: `aiops_runbook`
- 告警名称: `RedisHitRateLow`
- 告警分类: `缓存异常`
- 告警级别: `warning`
- 服务名称: `rag-agent`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `ai-team`
- 日志主题: `application-logs`
- 指标 Job: `rag-agent`

## 触发条件

Redis 命中率连续 10 分钟低于 80%

## 症状描述

数据库查询量上升，接口延迟增加，缓存 miss 日志增多。

## 推荐 PromQL

- `redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)`
- `rate(redis_commands_processed_total[5m])`

## 推荐日志查询

- `cache_miss:true OR cache_penetration:true`
- `redis timeout OR redis connection refused`

## 常见根因

- 缓存批量过期导致击穿
- 缓存 key 设计不合理或版本变化
- 热点数据未预热
- 恶意或异常参数造成缓存穿透

## 立即处置

1. 预热热点 key 并延长 TTL
2. 对空值结果设置短 TTL 缓存
3. 启用布隆过滤器或参数校验
4. 必要时限流保护数据库

## 诊断步骤

1. 查看命中率、miss 数、数据库 QPS 同步变化
2. 按 key 前缀统计 miss TopN
3. 检查发布后 key 规则是否变更
4. 确认热点 key 是否同时过期

## 验证标准

- 缓存命中率恢复到 90% 以上
- 数据库 QPS 回落到正常水平
- 接口 P99 延迟恢复

## 预防措施

- TTL 增加随机抖动
- 热点数据发布前预热
- 缓存 key 规则纳入兼容性测试

## Agent 使用提示

当用户询问 `rag-agent` 的 `RedisHitRateLow`、`缓存异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
