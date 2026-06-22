# api-gateway CPU 使用率过高处理手册

## 文档信息

- 文档类型: 运维处理手册
- 服务名称: api-gateway
- 告警名称: HighCPUUsage
- 告警级别: warning
- 测试关键词: OnCallUploadDemo20260618
- 适用场景: API 网关 CPU 使用率持续升高、接口响应变慢、请求超时增多

## 问题现象

当 `api-gateway` 出现 CPU 使用率过高时，通常会伴随以下现象：

- 请求响应时间明显升高。
- P95 或 P99 延迟超过历史基线。
- 网关日志中出现 `timeout`、`slow_request`、`upstream timeout` 等关键词。
- 部分接口返回 5xx。
- 线程池队列长度增加，请求开始排队。

## 常见原因

`api-gateway` CPU 使用率过高通常由以下原因造成：

- 上游流量突增，网关实例处理能力不足。
- 某个接口出现热点请求，导致单个路由 CPU 消耗异常。
- 下游服务响应变慢，网关连接和线程被长时间占用。
- 日志级别过高，短时间输出大量日志。
- 最近发布的新版本引入了高 CPU 消耗逻辑。
- 限流、鉴权、路由规则配置不合理。

## 排查步骤

1. 先查看 Prometheus 当前是否存在 `HighCPUUsage` 或网关相关告警。
2. 查询 `api-gateway` 最近 15 分钟 CPU 曲线，确认是单实例异常还是整体上涨。
3. 使用 CLS 查询最近 15 分钟错误日志，关键词可以包括：
   - `timeout`
   - `slow_request`
   - `upstream timeout`
   - `too many requests`
   - `thread_pool`
4. 查看最近是否有发布、配置变更或流量入口变化。
5. 对比 QPS、错误率、P99 延迟三条曲线，判断是流量问题还是下游阻塞问题。

## 推荐 CLS 查询

可以优先查询最近 15 分钟的错误日志：

```text
level:ERROR OR timeout OR slow_request OR upstream timeout
```

如果错误日志过多，可以缩小到网关服务关键词：

```text
api-gateway AND level:ERROR AND timeout
```

## 推荐 PromQL

可以使用以下 PromQL 观察 CPU 和请求趋势：

```promql
super_biz_agent_system_cpu_percent
```

```promql
rate(http_requests_total{job="api-gateway"}[5m])
```

```promql
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="api-gateway"}[5m])) by (le))
```

## 临时处理方案

如果 CPU 已经影响业务，可以按以下顺序处理：

1. 如果只有单个实例异常，先摘除异常实例。
2. 如果所有实例 CPU 都高，优先水平扩容 `api-gateway`。
3. 对非核心接口开启临时限流。
4. 降低非必要日志输出级别。
5. 如果与最近发布强相关，优先回滚发布版本。
6. 如果下游服务变慢，先对异常下游调用做熔断或降级。

## 恢复验证

处理后需要确认以下指标恢复：

- CPU 使用率回落到 60% 以下。
- P99 延迟恢复到历史基线。
- 5xx 错误率不再上升。
- CLS 中不再持续出现 `timeout` 或 `slow_request`。
- Prometheus 告警状态从 firing 或 pending 恢复正常。

## 预防建议

- 为核心接口配置限流和熔断。
- 为网关增加按路由维度的延迟和错误率监控。
- 发布前压测高频接口。
- 将大流量接口拆分独立网关或独立路由。
- 定期复盘高 CPU 告警，沉淀常见根因和处理动作。

## Agent 使用提示

当用户询问 `api-gateway CPU 高怎么处理`、`HighCPUUsage`、`网关响应慢`、
`接口超时变多` 或测试关键词 `OnCallUploadDemo20260618` 时，应优先召回本文档，
并结合 Prometheus 告警、CLS 日志和当前系统指标生成诊断建议。
