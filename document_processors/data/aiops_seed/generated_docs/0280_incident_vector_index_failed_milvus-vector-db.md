# milvus-vector-db - VectorIndexBuildFailed 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0280-vector_index_failed-milvus-vector-db`
- 数据类型: `aiops_incident_case`
- 告警名称: `VectorIndexBuildFailed`
- 告警分类: `向量库异常`
- 告警级别: `critical`
- 受影响服务: `milvus-vector-db`
- 命名空间: `prod`
- 责任团队: `ai-team`

## 事件摘要

`milvus-vector-db` 触发 `VectorIndexBuildFailed`，触发条件为：向量索引构建任务失败或超过 30 分钟未完成。
用户侧表现为：新增知识无法检索，RAG 回答缺少最新文档内容。

## 关键证据

### 指标证据

- 推荐查询: `increase(vector_index_failures_total{service="$service"}[30m])`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `index build failed OR MilvusException OR dimension mismatch`
- 日志主题: `milvus-logs`
- 证据模式: 日志中出现与 `VectorIndexBuildFailed` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：向量维度和 collection schema 不匹配

## 处置过程

1. 确认 embedding 维度和 Milvus schema 一致
2. 检查 collection 状态和连接配置
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 新增文档可以被相似度检索命中
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
