# mysql-primary - SlowResponse 运维处置知识

## 元数据

- 文档ID: `AIOPS-0049-slow_response-mysql-primary`
- 数据类型: `aiops_runbook`
- 告警名称: `SlowResponse`
- 告警分类: `性能异常`
- 告警级别: `warning`
- 服务名称: `mysql-primary`
- 服务角色: `db`
- 命名空间: `prod`
- 责任团队: `dba-team`
- 日志主题: `database-logs`
- 指标 Job: `mysql`

## 触发条件

P99 响应时间连续 5 分钟超过 3 秒

## 症状描述

用户请求明显变慢，部分请求超时，下游调用耗时升高。

## 推荐 PromQL

- `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))`
- `sum(rate(http_requests_total{service="$service",status=~"5.."}[5m]))`

## 推荐日志查询

- `response_time:>3000 OR timeout:true`
- `slow_query:true OR upstream_timeout:true`

## 常见根因

- 数据库慢查询或缺少索引
- 下游接口响应慢或超时
- 缓存命中率下降导致数据库压力上升
- 线程池耗尽或连接池耗尽

## 立即处置

1. 启用降级策略保护核心链路
2. 临时扩容慢服务实例
3. 对热点接口启用缓存或提高缓存 TTL
4. 对异常下游启用熔断和超时控制

## 诊断步骤

1. 按接口维度查看 P95/P99 和错误率
2. 查询慢 SQL、下游调用耗时和超时日志
3. 检查缓存命中率、连接池和线程池指标
4. 确认是否有发布、配置或流量变化

## 验证标准

- P99 延迟低于 1 秒或恢复到业务基线
- 超时错误数量不再增长
- 核心链路成功率恢复正常

## 预防措施

- 建立慢接口 TopN 看板
- 为外部依赖设置合理超时、重试和熔断
- 上线前执行容量评估和压测

## Agent 使用提示

当用户询问 `mysql-primary` 的 `SlowResponse`、`性能异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
