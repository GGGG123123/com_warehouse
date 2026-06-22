# Generated AIOps Seed Data

本目录由 `scripts/generate_aiops_seed_data.py` 自动生成。

- Markdown 文档数量: 329
- 用途: 作为 AIOps/RAG 知识库种子数据
- 推荐入库方式: 调用项目接口 `/api/index_directory`，目录参数传 `data/aiops_seed/generated_docs`

这些文档覆盖资源异常、性能异常、业务错误、数据库、缓存、消息队列、Kubernetes、
磁盘、Milvus 向量数据库等常见运维场景。
