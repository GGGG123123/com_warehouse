"""把 OCR Markdown 切分后的 chunks 写入项目 Milvus 数据库。

这个脚本是真正的“入库脚本”，会执行:
    1. 读取 ocr_md_milvus_chunks.jsonl；
    2. 调用项目里的 embedding 服务，把 content 转成向量；
    3. 写入 Milvus 的 biz collection。

运行前请确认:
    1. 已运行:
        python document_processors/ocr_md_milvus_chunk_splitter.py

    2. Milvus 已启动。

    3. 项目 .env 中 DASHSCOPE_API_KEY 已配置。

    4. 使用项目虚拟环境运行。

注意:
    本脚本不再切分 Markdown。
    它只负责把 JSONL 中的 chunk 写入 Milvus。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# =============================================================================
# 输入配置
# =============================================================================

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR = CURRENT_DIR / "data"

# 这个文件由 ocr_md_milvus_chunk_splitter.py 生成。
INPUT_CHUNKS_PATH = DATA_DIR / "ocr_md" / "ocr_md_milvus_chunks.jsonl"

# DashScope text-embedding-v4 当前批量条数限制比较小。
# 你的项目之前报过 batch size 不能超过 10，所以这里固定用 10。
BATCH_SIZE = 10

# True: 入库前按 metadata["_source"] 删除同一个 md 文件的旧 chunk，避免重复。
DELETE_OLD_BY_SOURCE = True

# True: 只校验 JSONL，不连接 Milvus，不调用 embedding。
# False: 真正写入 Milvus。
DRY_RUN = False

# 与 app/core/milvus_client.py 保持一致。
MILVUS_ID_MAX_LENGTH = 100
MILVUS_CONTENT_MAX_LENGTH = 8000


# =============================================================================
# 项目依赖导入
# =============================================================================


def ensure_project_root_on_path() -> None:
    """确保脚本可以 import 项目根目录下的 app 包。"""
    project_root_text = str(PROJECT_ROOT)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


def import_project_dependencies() -> tuple[Any, Any]:
    """导入 Milvus 入库需要的项目依赖。"""
    ensure_project_root_on_path()

    try:
        from langchain_core.documents import Document
        from app.services.vector_store_manager import vector_store_manager
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "缺少项目依赖，请使用项目虚拟环境运行，例如:\n"
            f"{PROJECT_ROOT}\\.venv\\Scripts\\python.exe "
            "document_processors\\ocr_md_milvus_indexer.py"
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            "项目配置不完整，请检查 .env 里的 DASHSCOPE_API_KEY 是否已配置。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            "导入项目向量服务失败，请确认 Milvus 已启动，且 .env 配置正确。"
        ) from exc

    return Document, vector_store_manager


# =============================================================================
# JSONL 读取和校验
# =============================================================================


def load_chunk_items(path: Path) -> list[dict[str, Any]]:
    """读取 splitter 生成的 JSONL chunk 文件。"""
    if not path.exists():
        raise FileNotFoundError(
            f"找不到 chunk 文件: {path}\n"
            "请先运行: python document_processors\\ocr_md_milvus_chunk_splitter.py"
        )

    items: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue

            try:
                item = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"chunk JSONL 第 {line_no} 行解析失败: {exc}") from exc

            validate_chunk_item(item, line_no)
            items.append(item)

    if not items:
        raise ValueError(f"chunk 文件为空: {path}")

    return items


def validate_chunk_item(item: dict[str, Any], line_no: int) -> None:
    """校验单条 chunk 是否符合 Milvus collection 字段限制。"""
    chunk_id = str(item.get("id") or "").strip()
    content = str(item.get("content") or "").strip()
    metadata = item.get("metadata")

    if not chunk_id:
        raise ValueError(f"chunk JSONL 第 {line_no} 行缺少 id")

    if len(chunk_id) > MILVUS_ID_MAX_LENGTH:
        raise ValueError(
            f"chunk JSONL 第 {line_no} 行 id 过长: {len(chunk_id)} > {MILVUS_ID_MAX_LENGTH}"
        )

    if not content:
        raise ValueError(f"chunk JSONL 第 {line_no} 行 content 为空")

    if len(content) > MILVUS_CONTENT_MAX_LENGTH:
        raise ValueError(
            f"chunk JSONL 第 {line_no} 行 content 过长: "
            f"{len(content)} > {MILVUS_CONTENT_MAX_LENGTH}"
        )

    if not isinstance(metadata, dict):
        raise ValueError(f"chunk JSONL 第 {line_no} 行 metadata 必须是 JSON 对象")


def find_duplicate_ids(items: list[dict[str, Any]]) -> list[str]:
    """检查 Milvus 主键 id 是否重复。"""
    seen: set[str] = set()
    duplicates: list[str] = []

    for item in items:
        chunk_id = str(item["id"])
        if chunk_id in seen:
            duplicates.append(chunk_id)
        else:
            seen.add(chunk_id)

    return duplicates


def get_source_for_delete(items: list[dict[str, Any]]) -> str:
    """获取 metadata['_source']，用于删除同一来源文件的旧数据。"""
    for item in items:
        metadata = item.get("metadata") or {}
        source = metadata.get("_source")
        if source:
            return str(source)
    return ""


def build_documents_and_ids(items: list[dict[str, Any]], Document: Any) -> tuple[list[Any], list[str]]:
    """把 JSONL chunk 转成 LangChain Document 和 Milvus ids。"""
    documents: list[Any] = []
    ids: list[str] = []

    for item in items:
        chunk_id = str(item["id"])
        content = str(item["content"])
        metadata = dict(item["metadata"])

        # 把 chunk_id 也放入 metadata，方便检索结果定位。
        metadata["chunk_id"] = chunk_id

        documents.append(Document(page_content=content, metadata=metadata))
        ids.append(chunk_id)

    return documents, ids


def batched(items: list[Any], batch_size: int) -> list[list[Any]]:
    """把列表拆成多个批次。"""
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


# =============================================================================
# Milvus 入库主流程
# =============================================================================


def index_chunks_to_milvus() -> None:
    """读取 OCR Markdown chunks，并写入 Milvus。"""
    print("开始读取 OCR Markdown Milvus chunks")
    print(f"输入文件: {INPUT_CHUNKS_PATH}")

    items = load_chunk_items(INPUT_CHUNKS_PATH)
    duplicate_ids = find_duplicate_ids(items)
    if duplicate_ids:
        raise ValueError(f"发现重复 chunk id，示例: {duplicate_ids[:5]}")

    print(f"待入库 chunk 数: {len(items)}")

    if DRY_RUN:
        print("DRY_RUN=True，只校验文件，不连接 Milvus，不调用 embedding。")
        return

    Document, vector_store_manager = import_project_dependencies()
    documents, ids = build_documents_and_ids(items, Document)

    if DELETE_OLD_BY_SOURCE:
        source_for_delete = get_source_for_delete(items)
        if source_for_delete:
            print(f"开始删除旧数据，metadata['_source']: {source_for_delete}")
            deleted_count = vector_store_manager.delete_by_source(source_for_delete)
            print(f"旧数据删除完成，删除数量: {deleted_count}")
        else:
            print("没有找到 metadata['_source']，跳过旧数据删除。")

    vector_store = vector_store_manager.get_vector_store()
    document_batches = batched(documents, BATCH_SIZE)
    id_batches = batched(ids, BATCH_SIZE)

    inserted_count = 0
    total_batches = len(document_batches)

    print("开始写入 Milvus，这一步会调用 embedding，请耐心等待。")

    for batch_index, (document_batch, id_batch) in enumerate(
        zip(document_batches, id_batches), start=1
    ):
        vector_store.add_documents(document_batch, ids=id_batch)
        inserted_count += len(document_batch)
        print(
            f"已写入批次 {batch_index}/{total_batches}，"
            f"本批 {len(document_batch)} 条，累计 {inserted_count} 条"
        )

    print("OCR Markdown Milvus 入库完成")
    print("collection: biz")
    print(f"写入 chunk 数: {inserted_count}")


def main() -> None:
    """脚本入口。"""
    try:
        index_chunks_to_milvus()
    except Exception as exc:
        print("OCR Markdown Milvus 入库失败")
        print(str(exc))
        raise


if __name__ == "__main__":
    main()
