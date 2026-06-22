"""验证前端上传的文件是否已经写入 Milvus。

使用方式:
    1. 先通过页面上传一个 .md 或 .txt 文件；
    2. 修改下面的 UPLOADED_FILE_NAME；
    3. 运行本脚本。

运行:
    .venv\\Scripts\\python.exe document_processors\\verify_uploaded_file_in_milvus.py

验证逻辑:
    - 先按 metadata["_source"] 查询 Milvus，确认该文件对应的 chunk 数；
    - 再用 TEST_QUERY 做一次向量召回，确认 RAG 能召回该文件内容。
"""

from __future__ import annotations

import sys
from pathlib import Path


# =============================================================================
# 你只需要改这里
# =============================================================================

# 这里填你上传后的文件名。
# 如果你上传的是我给你的示例文件，就保持这个值不变。
UPLOADED_FILE_NAME = "api_gateway_cpu_high_upload_demo.md"

# 用来测试向量召回的查询词。
# 示例文件里包含这个唯一关键词，适合验证是否真的入库。
TEST_QUERY = "OnCallUploadDemo20260618"

# 查询返回多少条样例。
LIMIT = 5


# =============================================================================
# 项目路径
# =============================================================================

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
UPLOADS_DIR = PROJECT_ROOT / "uploads"


def ensure_project_root_on_path() -> None:
    """保证脚本可以 import app 包。"""
    project_root_text = str(PROJECT_ROOT)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


def main() -> None:
    """执行验证。"""
    ensure_project_root_on_path()

    from app.core.milvus_client import milvus_manager
    from app.services.vector_search_service import vector_search_service

    uploaded_path = (UPLOADS_DIR / UPLOADED_FILE_NAME).resolve()
    normalized_source = uploaded_path.as_posix()

    print("开始验证上传文件是否已写入 Milvus")
    print(f"上传文件路径: {uploaded_path}")
    print(f"Milvus metadata['_source']: {normalized_source}")

    if not uploaded_path.exists():
        print("本地 uploads 目录中没有找到该文件。")
        print("请先通过页面上传，或者检查 UPLOADED_FILE_NAME 是否写错。")
        return

    milvus_manager.connect()
    collection = milvus_manager.get_collection()
    collection.load()

    expr = f'metadata["_source"] == "{normalized_source}"'
    rows = collection.query(
        expr=expr,
        output_fields=["id", "content", "metadata"],
        limit=LIMIT,
    )

    count_result = collection.query(
        expr=expr,
        output_fields=["count(*)"],
    )

    chunk_count = 0
    if count_result and "count(*)" in count_result[0]:
        chunk_count = int(count_result[0]["count(*)"])

    print(f"按文件来源查到的 chunk 数: {chunk_count}")

    if not rows:
        print("没有查到该文件对应的 Milvus 数据。")
        print("可能原因: 上传时 embedding/入库失败，或者该文件名不是上传后的安全文件名。")
        return

    print("\nMilvus 样例记录:")
    for index, row in enumerate(rows, start=1):
        metadata = row.get("metadata") or {}
        content = (row.get("content") or "").replace("\n", " ")
        print("-" * 80)
        print(f"样例 {index}")
        print(f"id: {row.get('id')}")
        print(f"file_name: {metadata.get('_file_name')}")
        print(f"extension: {metadata.get('_extension')}")
        print(f"content_preview: {content[:300]}")

    print("\n开始测试向量召回")
    results = vector_search_service.search_similar_documents(TEST_QUERY, top_k=3)
    for index, result in enumerate(results, start=1):
        metadata = result.metadata or {}
        content = result.content.replace("\n", " ")
        print("-" * 80)
        print(f"召回 {index}")
        print(f"id: {result.id}")
        print(f"score: {result.score}")
        print(f"file_name: {metadata.get('_file_name')}")
        print(f"source: {metadata.get('_source')}")
        print(f"content_preview: {content[:300]}")


if __name__ == "__main__":
    main()
