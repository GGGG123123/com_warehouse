# api-gateway - HighCPUUsage 运维处置知识

## 元数据

- 文档ID: `AIOPS-0001-high_cpu-api-gateway`
- 数据类型: `aiops_runbook`
- 告警名称: `HighCPUUsage`
- 告警分类: `资源异常`
- 告警级别: `critical`
- 服务名称: `api-gateway`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `platform-team`
- 日志主题: `application-logs`
- 指标 Job: `api-gateway`

## 触发条件

CPU 使用率连续 5 分钟超过 85%

## 症状描述

实例负载升高、接口响应变慢、请求排队增加，严重时出现超时。

## 推荐 PromQL

- `avg(rate(container_cpu_usage_seconds_total{pod=~"$pod"}[5m])) by (pod)`
- `node_load1{instance="$instance"}`

## 推荐日志查询

- `level:ERROR OR cpu_usage:>85`
- `thread_pool_queue_size:>100 OR slow_request:true`

## 常见根因

- 流量突增导致业务线程持续满载
- 代码死循环或热点方法 CPU 消耗异常
- 慢 SQL 或外部接口阻塞导致请求堆积
- 定时任务和在线流量重叠执行

## 立即处置

1. 确认是否单实例异常，必要时摘除异常实例
2. 如果整体流量上涨，优先水平扩容
3. 开启限流或降级非核心接口
4. 保留线程栈和关键日志后再重启

## 诊断步骤

1. 查询最近 30 分钟 CPU、QPS、P99 延迟变化趋势
2. 查询同时间窗口应用错误日志和慢请求日志
3. 检查线程池、连接池和下游依赖耗时
4. 对比发布记录、定时任务和流量入口变化

## 验证标准

- CPU 使用率回落到 60% 以下
- P99 延迟恢复到基线范围
- 错误率和超时数量不再增长

## 预防措施

- 为热点接口增加限流和熔断
- 补充 CPU 火焰图和线程池队列监控
- 将重任务迁移到异步队列或离峰执行

## Agent 使用提示

当用户询问 `api-gateway` 的 `HighCPUUsage`、`资源异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
