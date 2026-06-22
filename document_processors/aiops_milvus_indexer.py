"""把 AIOps Milvus chunks 写入项目的 Milvus 数据库。

这个脚本是真正的“入库脚本”，会做三件事:
    1. 读取 aiops_seed_milvus_chunks.jsonl；
    2. 调用项目里的 DashScope embedding 服务，把 content 转成向量；
    3. 写入 Milvus 的 biz collection。

运行前请确认:
    1. 已经运行过:
        python document_processors/aiops_milvus_chunk_splitter.py

    2. Milvus 已经启动。

    3. 项目 .env 里已经配置 DASHSCOPE_API_KEY。

    4. 推荐使用项目虚拟环境运行:
        C:\\Users\\Administrator\\Desktop\\agent源代码\\super_biz_agent_py-release-2026-05-17\\.venv\\Scripts\\python.exe document_processors\\aiops_milvus_indexer.py

说明:
    这个脚本不会再次切分文本。
    aiops_seed_milvus_chunks.jsonl 里每一行就是一个要入 Milvus 的 chunk。

入库字段对应关系:
    chunk["id"]       -> Milvus 主键字段 id
    chunk["content"]  -> Milvus 文本字段 content，并用于 embedding
    embedding 向量     -> Milvus 向量字段 vector
    chunk["metadata"] -> Milvus JSON 字段 metadata
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# =============================================================================
# 输入配置
# =============================================================================

# 当前文件所在目录:
# C:\Users\Administrator\Desktop\agent源代码\super_biz_agent_py-release-2026-05-17\document_processors
CURRENT_DIR = Path(__file__).resolve().parent

# 项目根目录:
# C:\Users\Administrator\Desktop\agent源代码\super_biz_agent_py-release-2026-05-17
PROJECT_ROOT = CURRENT_DIR.parent

# document_processors/data 目录。
DATA_DIR = CURRENT_DIR / "data"

# 前一步 aiops_milvus_chunk_splitter.py 生成的 chunk 文件。
INPUT_CHUNKS_PATH = DATA_DIR / "aiops_seed" / "aiops_seed_milvus_chunks.jsonl"

# 每批写入多少条。
# DashScope text-embedding-v4 当前单次最多允许 10 条 input.contents。
# 这里设置为 10，避免出现 batch size is invalid。
BATCH_SIZE = 10

# 是否先删除同一批旧数据。
# True: 先按 metadata["_source"] 删除旧 chunk，避免重复入库。
# False: 不删除旧数据，如果 id 重复，Milvus 可能会报主键冲突。
DELETE_OLD_BY_SOURCE = True

# 是否只预览不入库。
# False: 真正写入 Milvus。
# True: 只读取和校验 JSONL，不调用 embedding，不连接 Milvus。
DRY_RUN = False

# Milvus collection 里 id 字段最大长度。
# 这个值来自 app/core/milvus_client.py 里的 ID_MAX_LENGTH。
MILVUS_ID_MAX_LENGTH = 100

# Milvus collection 里 content 字段最大长度。
# 这个值来自 app/core/milvus_client.py 里的 CONTENT_MAX_LENGTH。
MILVUS_CONTENT_MAX_LENGTH = 8000


# =============================================================================
# 路径与依赖处理
# =============================================================================


def ensure_project_root_on_path() -> None:
    """确保脚本无论从哪里运行，都能 import 项目的 app 包。

    如果直接运行:
        python C:\\...\\document_processors\\aiops_milvus_indexer.py

    Python 默认会把 document_processors 放到 sys.path，
    但不一定能找到项目根目录下的 app 包。
    所以这里手动把 PROJECT_ROOT 加进去。
    """
    project_root_text = str(PROJECT_ROOT)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


def import_project_dependencies() -> tuple[Any, Any]:
    """导入项目入库需要的依赖。

    放在函数里导入，是为了在依赖缺失时给出更清楚的提示。
    """
    ensure_project_root_on_path()

    try:
        from langchain_core.documents import Document
        from app.services.vector_store_manager import vector_store_manager
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "缺少项目依赖，请使用项目虚拟环境运行，例如:\n"
            f"{PROJECT_ROOT}\\.venv\\Scripts\\python.exe "
            "document_processors\\aiops_milvus_indexer.py"
        ) from exc
    except ValueError as exc:
        # vector_embedding_service 在导入时会检查 DASHSCOPE_API_KEY。
        raise RuntimeError(
            "项目配置不完整，请检查 .env 里的 DASHSCOPE_API_KEY 是否已配置。"
        ) from exc
    except Exception as exc:
        # 这里可能是 Milvus 没启动，也可能是连接参数不对。
        raise RuntimeError(
            "导入项目向量服务失败，请确认 Milvus 已启动，且 .env 配置正确。"
        ) from exc

    return Document, vector_store_manager


# =============================================================================
# JSONL 读取与校验
# =============================================================================


def load_chunk_items(path: Path) -> list[dict[str, Any]]:
    """读取待入库 chunk JSONL。

    每一行必须包含:
        id: chunk 主键
        content: 用于 embedding 的文本
        metadata: 要写入 Milvus metadata 字段的 JSON
    """
    if not path.exists():
        raise FileNotFoundError(
            f"找不到 chunk 文件: {path}\n"
            "请先运行: python document_processors\\aiops_milvus_chunk_splitter.py"
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
    """校验单条 chunk 是否符合 Milvus 入库要求。"""
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
    """检查 chunk id 是否重复。"""
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
    """获取用于删除旧数据的 metadata['_source']。

    aiops_milvus_chunk_splitter.py 会在每条 metadata 里写入 _source。
    vector_store_manager.delete_by_source() 正是按这个字段删除旧数据。
    """
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

        # 把 chunk_id 再放入 metadata，方便检索结果展示和排查。
        metadata["chunk_id"] = chunk_id

        documents.append(Document(page_content=content, metadata=metadata))
        ids.append(chunk_id)

    return documents, ids


def batched(items: list[Any], batch_size: int) -> list[list[Any]]:
    """把列表按 batch_size 分批。"""
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


# =============================================================================
# Milvus 入库主流程
# =============================================================================


def index_chunks_to_milvus() -> None:
    """读取 chunks，并写入 Milvus。"""
    print("开始读取 AIOps Milvus chunks")
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

    print("开始写入 Milvus，这一步会调用 DashScope embedding，请耐心等待。")

    for batch_index, (document_batch, id_batch) in enumerate(
        zip(document_batches, id_batches), start=1
    ):
        # LangChain Milvus 会自动:
        #   1. 调用 embedding_function.embed_documents()
        #   2. 把向量写入 vector 字段
        #   3. 把文本写入 content 字段
        #   4. 把 metadata 写入 metadata JSON 字段
        vector_store.add_documents(document_batch, ids=id_batch)

        inserted_count += len(document_batch)
        print(
            f"已写入批次 {batch_index}/{total_batches}，"
            f"本批 {len(document_batch)} 条，累计 {inserted_count} 条"
        )

    print("Milvus 入库完成")
    print(f"collection: biz")
    print(f"写入 chunk 数: {inserted_count}")


def main() -> None:
    """脚本入口。"""
    try:
        index_chunks_to_milvus()
    except Exception as exc:
        print("Milvus 入库失败")
        print(str(exc))
        raise


if __name__ == "__main__":
    main()
