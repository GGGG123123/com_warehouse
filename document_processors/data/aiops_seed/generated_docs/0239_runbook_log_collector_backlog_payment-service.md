# payment-service - LogCollectorBacklogHigh 运维处置知识

## 元数据

- 文档ID: `AIOPS-0239-log_collector_backlog-payment-service`
- 数据类型: `aiops_runbook`
- 告警名称: `LogCollectorBacklogHigh`
- 告警分类: `日志采集异常`
- 告警级别: `warning`
- 服务名称: `payment-service`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `payment-team`
- 日志主题: `application-logs`
- 指标 Job: `payment-service`

## 触发条件

日志采集队列积压连续 10 分钟增长

## 症状描述

日志查询延迟，告警诊断缺少最新日志证据。

## 推荐 PromQL

- `collector_queue_size{job="$job"}`
- `rate(collector_dropped_logs_total{job="$job"}[5m])`

## 推荐日志查询

- `collector backlog OR send failed OR retry`
- `rate limit exceeded OR log dropped`

## 常见根因

- 日志量突增超过采集吞吐
- 日志服务写入限流
- 网络抖动导致发送失败重试
- 采集 Agent 资源不足

## 立即处置

1. 扩容采集 Agent 或提高发送并发
2. 临时降低 DEBUG 日志量
3. 检查日志服务限流和配额
4. 优先保留 ERROR/WARN 关键日志

## 诊断步骤

1. 查看采集队列长度、丢弃量和发送失败率
2. 按服务统计日志量 TopN
3. 检查日志服务写入响应码
4. 确认最近是否开启了详细日志

## 验证标准

- 采集队列持续下降
- 日志写入失败率归零
- 查询延迟恢复正常

## 预防措施

- 控制生产环境 DEBUG 日志
- 为高日志量服务设置采样策略
- 日志配额随业务峰值做容量规划

## Agent 使用提示

当用户询问 `payment-service` 的 `LogCollectorBacklogHigh`、`日志采集异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
