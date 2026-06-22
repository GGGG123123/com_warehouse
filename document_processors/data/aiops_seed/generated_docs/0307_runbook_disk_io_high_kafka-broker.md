# kafka-broker - DiskIOHigh 运维处置知识

## 元数据

- 文档ID: `AIOPS-0307-disk_io_high-kafka-broker`
- 数据类型: `aiops_runbook`
- 告警名称: `DiskIOHigh`
- 告警分类: `存储异常`
- 告警级别: `warning`
- 服务名称: `kafka-broker`
- 服务角色: `queue`
- 命名空间: `prod`
- 责任团队: `platform-team`
- 日志主题: `kafka-logs`
- 指标 Job: `kafka`

## 触发条件

磁盘 IO 使用率连续 10 分钟超过 80%

## 症状描述

读写延迟升高，数据库或日志写入变慢，应用响应抖动。

## 推荐 PromQL

- `rate(node_disk_io_time_seconds_total[5m])`
- `rate(node_disk_read_time_seconds_total[5m]) + rate(node_disk_write_time_seconds_total[5m])`

## 推荐日志查询

- `i/o timeout OR disk io high OR fsync slow`
- `slow write OR WAL sync slow OR segment flush slow`

## 常见根因

- 数据库 checkpoint、WAL 或 compaction 压力
- 日志写入量突增
- 批量导入或备份任务占用磁盘
- 磁盘性能不足或云盘抖动

## 立即处置

1. 暂停低优先级导入、备份或压缩任务
2. 将日志写入和数据盘隔离
3. 扩容磁盘 IOPS 或升级磁盘规格
4. 降低写入批量并增加缓冲

## 诊断步骤

1. 查看磁盘 util、await、读写吞吐和 IOPS
2. 定位占用 IO 最高的进程和目录
3. 检查数据库 checkpoint/compaction 日志
4. 确认备份、导入、日志采集任务时间线

## 验证标准

- 磁盘 util 低于 60%
- 读写 await 恢复到基线
- 业务延迟抖动消失

## 预防措施

- IO 密集任务离峰执行
- 关键数据库使用独立高性能磁盘
- 建立磁盘延迟而不仅是容量告警

## Agent 使用提示

当用户询问 `kafka-broker` 的 `DiskIOHigh`、`存储异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
