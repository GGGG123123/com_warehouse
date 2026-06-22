# VectorIndexBuildFailed 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0327-vector_index_failed`
- 数据类型: `aiops_alert_rule`
- 告警名称: `VectorIndexBuildFailed`
- 告警分类: `向量库异常`
- 默认级别: `critical`

## 告警语义

向量索引构建任务失败或超过 30 分钟未完成

## 适用场景

新增知识无法检索，RAG 回答缺少最新文档内容。

## 推荐 PromQL 模板

- `increase(vector_index_failures_total{service="$service"}[30m])`
- `vector_index_pending_tasks{service="$service"}`

## 推荐日志查询模板

- `index build failed OR MilvusException OR dimension mismatch`
- `collection not found OR insert failed OR embedding dimension`

## 根因候选

- 向量维度和 collection schema 不匹配
- Milvus collection 不存在或未加载
- 批量写入过大导致超时
- 源文档格式异常或内容为空

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `VectorIndexBuildFailed`、`向量库异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
