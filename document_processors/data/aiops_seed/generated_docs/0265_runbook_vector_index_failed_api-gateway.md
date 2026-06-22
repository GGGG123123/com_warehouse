# api-gateway - VectorIndexBuildFailed 运维处置知识

## 元数据

- 文档ID: `AIOPS-0265-vector_index_failed-api-gateway`
- 数据类型: `aiops_runbook`
- 告警名称: `VectorIndexBuildFailed`
- 告警分类: `向量库异常`
- 告警级别: `critical`
- 服务名称: `api-gateway`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `platform-team`
- 日志主题: `application-logs`
- 指标 Job: `api-gateway`

## 触发条件

向量索引构建任务失败或超过 30 分钟未完成

## 症状描述

新增知识无法检索，RAG 回答缺少最新文档内容。

## 推荐 PromQL

- `increase(vector_index_failures_total{service="$service"}[30m])`
- `vector_index_pending_tasks{service="$service"}`

## 推荐日志查询

- `index build failed OR MilvusException OR dimension mismatch`
- `collection not found OR insert failed OR embedding dimension`

## 常见根因

- 向量维度和 collection schema 不匹配
- Milvus collection 不存在或未加载
- 批量写入过大导致超时
- 源文档格式异常或内容为空

## 立即处置

1. 确认 embedding 维度和 Milvus schema 一致
2. 检查 collection 状态和连接配置
3. 降低批量写入大小后重试
4. 隔离格式异常的源文档

## 诊断步骤

1. 查看向量索引任务日志中的首个异常
2. 查询 Milvus collection schema 和 load 状态
3. 检查 embedding 模型维度配置
4. 统计失败文档类型和文件大小

## 验证标准

- 失败任务重试成功
- 新增文档可以被相似度检索命中
- Milvus insert 和 search 日志无异常

## 预防措施

- 入库前做文档格式和维度校验
- 索引任务增加失败重试和死信记录
- collection schema 变更需要迁移计划

## Agent 使用提示

当用户询问 `api-gateway` 的 `VectorIndexBuildFailed`、`向量库异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
