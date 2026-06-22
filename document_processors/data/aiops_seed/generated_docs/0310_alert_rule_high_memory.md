# HighMemoryUsage 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0310-high_memory`
- 数据类型: `aiops_alert_rule`
- 告警名称: `HighMemoryUsage`
- 告警分类: `资源异常`
- 默认级别: `critical`

## 告警语义

内存使用率连续 5 分钟超过 85%

## 适用场景

内存持续上涨、GC 频繁、实例重启、可能触发 OOMKilled。

## 推荐 PromQL 模板

- `container_memory_working_set_bytes{pod=~"$pod"}`
- `increase(container_oom_events_total{pod=~"$pod"}[30m])`

## 推荐日志查询模板

- `OutOfMemoryError OR OOMKilled OR memory_usage:>85`
- `Full GC OR GC overhead OR heap dump`

## 根因候选

- 内存泄漏导致 Full GC 后无法回收
- 缓存容量或 TTL 配置不合理
- 批处理任务一次性加载大对象
- 实例规格过小或堆内存参数配置不合理

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `HighMemoryUsage`、`资源异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
