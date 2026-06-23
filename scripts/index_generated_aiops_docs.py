"""把生成的 AIOps Markdown 文档写入项目 Milvus 向量库。

运行前要求:
    1. Milvus 已启动；
    2. `.env` 中配置了 MODEL_API_KEY 和 MODEL_API_BASE；
    3. 已执行 `python scripts/generate_aiops_seed_data.py` 生成文档。

运行:
    python scripts/index_generated_aiops_docs.py
"""

from __future__ import annotations

from pathlib import Path

from app.services.vector_index_service import vector_index_service

# 这里使用项目现有的目录索引能力；只要目录下是 .md/.txt，就会自动分片、embedding、入 Milvus。
DOCS_DIR = Path("data/aiops_seed/generated_docs")


def main() -> None:
    """索引生成的 AIOps 文档目录。"""
    if not DOCS_DIR.exists():
        raise FileNotFoundError(f"目录不存在，请先生成数据: {DOCS_DIR}")

    result = vector_index_service.index_directory(str(DOCS_DIR))
    print(result.to_dict())


if __name__ == "__main__":
    main()
