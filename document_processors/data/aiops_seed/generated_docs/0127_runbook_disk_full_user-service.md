# user-service - DiskSpaceLow 运维处置知识

## 元数据

- 文档ID: `AIOPS-0127-disk_full-user-service`
- 数据类型: `aiops_runbook`
- 告警名称: `DiskSpaceLow`
- 告警分类: `存储异常`
- 告警级别: `critical`
- 服务名称: `user-service`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `user-team`
- 日志主题: `application-logs`
- 指标 Job: `user-service`

## 触发条件

磁盘使用率连续 10 分钟超过 90%

## 症状描述

日志无法写入、数据库写入失败、服务可能进入只读或崩溃。

## 推荐 PromQL

- `node_filesystem_avail_bytes{mountpoint="/"}`
- `100 - node_filesystem_avail_bytes / node_filesystem_size_bytes * 100`

## 推荐日志查询

- `No space left on device OR disk full`
- `log rotate failed OR write failed`

## 常见根因

- 日志滚动或清理策略失效
- 临时文件、导出文件或 dump 文件堆积
- 数据库 binlog、WAL 或 segment 文件增长
- 监控采集异常导致本地缓存堆积

## 立即处置

1. 清理可安全删除的临时文件和过期日志
2. 压缩或转移大文件
3. 扩大磁盘或挂载新卷
4. 暂停产生大量文件的任务

## 诊断步骤

1. du -xh --max-depth=1 定位大目录
2. 检查日志滚动配置和保留天数
3. 查看数据库日志、binlog、WAL 增长情况
4. 确认是否有异常 dump 或导出任务

## 验证标准

- 磁盘使用率低于 75%
- 服务写入日志和数据恢复正常
- 无新的 disk full 错误

## 预防措施

- 配置日志轮转和保留策略
- 为关键目录设置独立磁盘告警
- 建立大文件巡检和自动清理任务

## Agent 使用提示

当用户询问 `user-service` 的 `DiskSpaceLow`、`存储异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
