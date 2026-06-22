# milvus-vector-db - HighMemoryUsage 运维处置知识

## 元数据

- 文档ID: `AIOPS-0037-high_memory-milvus-vector-db`
- 数据类型: `aiops_runbook`
- 告警名称: `HighMemoryUsage`
- 告警分类: `资源异常`
- 告警级别: `critical`
- 服务名称: `milvus-vector-db`
- 服务角色: `vector_db`
- 命名空间: `prod`
- 责任团队: `ai-team`
- 日志主题: `milvus-logs`
- 指标 Job: `milvus`

## 触发条件

内存使用率连续 5 分钟超过 85%

## 症状描述

内存持续上涨、GC 频繁、实例重启、可能触发 OOMKilled。

## 推荐 PromQL

- `container_memory_working_set_bytes{pod=~"$pod"}`
- `increase(container_oom_events_total{pod=~"$pod"}[30m])`

## 推荐日志查询

- `OutOfMemoryError OR OOMKilled OR memory_usage:>85`
- `Full GC OR GC overhead OR heap dump`

## 常见根因

- 内存泄漏导致 Full GC 后无法回收
- 缓存容量或 TTL 配置不合理
- 批处理任务一次性加载大对象
- 实例规格过小或堆内存参数配置不合理

## 立即处置

1. 优先扩容或重启异常实例恢复服务
2. 重启前保留 heap dump 或内存快照
3. 降低缓存容量或临时清理热点缓存
4. 暂停大批量导入或离线任务

## 诊断步骤

1. 查看内存趋势是否持续单调上涨
2. 检查 OOM 事件、GC 次数和 GC 耗时
3. 定位最近发布是否引入大对象或缓存变更
4. 分析 heap dump 中占用最高的对象类型

## 验证标准

- 内存使用率稳定低于 70%
- Full GC 频率恢复正常
- 无新的 OOMKilled 或 OutOfMemoryError

## 预防措施

- 对缓存设置容量上限和淘汰策略
- 大文件处理改为流式或分批
- 上线前做内存压测和泄漏检查

## Agent 使用提示

当用户询问 `milvus-vector-db` 的 `HighMemoryUsage`、`资源异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
