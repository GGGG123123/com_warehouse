"""把预切分好的 AIOps chunks 写入 Milvus。

运行前要求:
    1. 已执行 `python scripts/split_aiops_seed_for_milvus.py`；
    2. Milvus 已启动；
    3. `.env` 中配置了 DASHSCOPE_API_KEY。

运行:
    python scripts/index_aiops_seed_milvus_chunks.py

说明:
    这个脚本不会再调用 DocumentSplitterService，因为输入文件已经是切好的 chunk。
    每个 chunk 的 content 用于 embedding，metadata 会写入 Milvus 的 JSON metadata 字段。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.services.vector_store_manager import vector_store_manager


# 由 scripts/split_aiops_seed_for_milvus.py 生成的预切分数据。
INPUT_CHUNKS_PATH = Path("data/aiops_seed/aiops_seed_milvus_chunks.jsonl")

# 控制单次 embedding 和入库的批大小。
# 当前 embedding 服务单次批量条数限制较小。
BATCH_SIZE = 10


def load_chunk_documents(path: Path) -> tuple[list[Document], list[str], str]:
    """读取 chunk JSONL，并转换成 LangChain Document。

    返回:
        documents: 待写入 Milvus 的文档对象
        ids: Milvus 主键 id，使用 chunk id，方便后续定位
        source_for_delete: 用于删除旧数据的 _source 值
    """
    documents: list[Document] = []
    ids: list[str] = []
    source_for_delete = ""

    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue

            try:
                item: dict[str, Any] = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"chunk JSONL 第 {line_no} 行解析失败: {exc}") from exc

            chunk_id = str(item.get("id") or "").strip()
            content = str(item.get("content") or "").strip()
            metadata = dict(item.get("metadata") or {})

            if not chunk_id:
                raise ValueError(f"chunk JSONL 第 {line_no} 行缺少 id")
            if not content:
                raise ValueError(f"chunk JSONL 第 {line_no} 行 content 为空")

            metadata["chunk_id"] = chunk_id
            source_for_delete = source_for_delete or metadata.get("_source", "")

            documents.append(Document(page_content=content, metadata=metadata))
            ids.append(chunk_id)

    return documents, ids, source_for_delete


def batched(items: list[Any], batch_size: int) -> list[list[Any]]:
    """把列表按固定大小切成多个批次。"""
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def main() -> None:
    """执行 Milvus 入库。"""
    if not INPUT_CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"找不到 chunk 文件，请先运行: python scripts/split_aiops_seed_for_milvus.py"
        )

    documents, ids, source_for_delete = load_chunk_documents(INPUT_CHUNKS_PATH)
    if not documents:
        print("没有可入库的 chunk")
        return

    # 先删除同一批数据的旧 chunk，避免重复入库。
    # delete_by_source 使用 metadata['_source'] 过滤，所以这里沿用 split 脚本写入的 _source。
    if source_for_delete:
        deleted_count = vector_store_manager.delete_by_source(source_for_delete)
        print(f"已删除旧 chunk 数: {deleted_count}")

    vector_store = vector_store_manager.get_vector_store()
    document_batches = batched(documents, BATCH_SIZE)
    id_batches = batched(ids, BATCH_SIZE)

    inserted_count = 0
    for batch_index, (document_batch, id_batch) in enumerate(
        zip(document_batches, id_batches), start=1
    ):
        vector_store.add_documents(document_batch, ids=id_batch)
        inserted_count += len(document_batch)
        print(f"已入库批次 {batch_index}/{len(document_batches)}，累计 {inserted_count}")

    print(f"Milvus 入库完成，总 chunk 数: {inserted_count}")


if __name__ == "__main__":
    main()
