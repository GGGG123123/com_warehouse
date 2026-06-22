# DiskIOHigh 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0329-disk_io_high`
- 数据类型: `aiops_alert_rule`
- 告警名称: `DiskIOHigh`
- 告警分类: `存储异常`
- 默认级别: `warning`

## 告警语义

磁盘 IO 使用率连续 10 分钟超过 80%

## 适用场景

读写延迟升高，数据库或日志写入变慢，应用响应抖动。

## 推荐 PromQL 模板

- `rate(node_disk_io_time_seconds_total[5m])`
- `rate(node_disk_read_time_seconds_total[5m]) + rate(node_disk_write_time_seconds_total[5m])`

## 推荐日志查询模板

- `i/o timeout OR disk io high OR fsync slow`
- `slow write OR WAL sync slow OR segment flush slow`

## 根因候选

- 数据库 checkpoint、WAL 或 compaction 压力
- 日志写入量突增
- 批量导入或备份任务占用磁盘
- 磁盘性能不足或云盘抖动

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `DiskIOHigh`、`存储异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
