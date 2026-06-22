# cls-collector - PrometheusScrapeFailure 运维处置知识

## 元数据

- 文档ID: `AIOPS-0233-prometheus_scrape_failure-cls-collector`
- 数据类型: `aiops_runbook`
- 告警名称: `PrometheusScrapeFailure`
- 告警分类: `监控异常`
- 告警级别: `warning`
- 服务名称: `cls-collector`
- 服务角色: `collector`
- 命名空间: `prod`
- 责任团队: `sre-team`
- 日志主题: `collector-logs`
- 指标 Job: `cls-collector`

## 触发条件

Prometheus target scrape 失败率连续 10 分钟超过 20%

## 症状描述

指标缺失，告警可能失真，监控看板出现断点。

## 推荐 PromQL

- `up{job="$job"} == 0`
- `sum(rate(prometheus_target_scrapes_exceeded_sample_limit_total[5m])) by (job)`

## 推荐日志查询

- `scrape failed OR context deadline exceeded`
- `sample limit exceeded OR target down`

## 常见根因

- 服务 metrics endpoint 不可达
- 采集超时或样本量过大
- 网络策略或安全组阻断
- Prometheus 负载过高

## 立即处置

1. 确认 target endpoint 是否可访问
2. 临时提高 scrape timeout 或降低采集频率
3. 修复网络策略或服务发现配置
4. 减少高基数指标暴露

## 诊断步骤

1. 查看 Prometheus targets 页面失败原因
2. 检查 target 服务健康状态
3. 查询 Prometheus 自身 CPU、内存和 TSDB 指标
4. 定位是否有高基数指标突增

## 验证标准

- target up 恢复为 1
- scrape duration 低于 timeout
- 看板指标断点恢复

## 预防措施

- 限制高基数 label
- 为核心 target 设置 scrape 失败告警
- Prometheus 按业务域拆分采集压力

## Agent 使用提示

当用户询问 `cls-collector` 的 `PrometheusScrapeFailure`、`监控异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
