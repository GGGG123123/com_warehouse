# DiskSpaceLow 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0317-disk_full`
- 数据类型: `aiops_alert_rule`
- 告警名称: `DiskSpaceLow`
- 告警分类: `存储异常`
- 默认级别: `critical`

## 告警语义

磁盘使用率连续 10 分钟超过 90%

## 适用场景

日志无法写入、数据库写入失败、服务可能进入只读或崩溃。

## 推荐 PromQL 模板

- `node_filesystem_avail_bytes{mountpoint="/"}`
- `100 - node_filesystem_avail_bytes / node_filesystem_size_bytes * 100`

## 推荐日志查询模板

- `No space left on device OR disk full`
- `log rotate failed OR write failed`

## 根因候选

- 日志滚动或清理策略失效
- 临时文件、导出文件或 dump 文件堆积
- 数据库 binlog、WAL 或 segment 文件增长
- 监控采集异常导致本地缓存堆积

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `DiskSpaceLow`、`存储异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
