# HighCPUUsage 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0309-high_cpu`
- 数据类型: `aiops_alert_rule`
- 告警名称: `HighCPUUsage`
- 告警分类: `资源异常`
- 默认级别: `critical`

## 告警语义

CPU 使用率连续 5 分钟超过 85%

## 适用场景

实例负载升高、接口响应变慢、请求排队增加，严重时出现超时。

## 推荐 PromQL 模板

- `avg(rate(container_cpu_usage_seconds_total{pod=~"$pod"}[5m])) by (pod)`
- `node_load1{instance="$instance"}`

## 推荐日志查询模板

- `level:ERROR OR cpu_usage:>85`
- `thread_pool_queue_size:>100 OR slow_request:true`

## 根因候选

- 流量突增导致业务线程持续满载
- 代码死循环或热点方法 CPU 消耗异常
- 慢 SQL 或外部接口阻塞导致请求堆积
- 定时任务和在线流量重叠执行

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `HighCPUUsage`、`资源异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
