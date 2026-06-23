# AIOps 运维种子数据

这个目录存放生成的 AIOps 运维知识库数据。

## 目录结构

- `generated_docs/`: Markdown 文档，适合直接进入项目现有 Milvus 向量库。
- `aiops_seed_records.jsonl`: 结构化 JSONL，保留每条数据的类型、告警名、服务名、责任团队等字段。

## 数据规模

当前生成内容包括：

- `aiops_runbook`: 运维处置知识。
- `aiops_incident_case`: 故障案例。
- `aiops_alert_rule`: 告警规则与诊断提示。

覆盖方向包括资源异常、性能异常、业务错误、数据库、缓存、消息队列、Kubernetes、
磁盘、Milvus、Prometheus、日志采集、Embedding API、证书、网关等场景。

## 重新生成

```bash
python scripts/generate_aiops_seed_data.py
```

## 写入向量库

确认 Milvus 已启动、`.env` 中已配置 `MODEL_API_KEY` 和 `MODEL_API_BASE` 后运行：

```bash
python scripts/index_generated_aiops_docs.py
```

也可以直接调用接口 `/api/index_directory`，目录参数传：

```text
data/aiops_seed/generated_docs
```
