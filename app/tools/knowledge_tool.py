"""知识检索工具 - 从向量数据库中检索相关信息"""

import re
from typing import Any, Dict, List, Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
from loguru import logger

from app.config import config
from app.core.milvus_client import milvus_manager


# 识别类似服务名、文件名、告警名、测试关键词这类“精确标识符”。
# 这类词只靠向量召回容易丢失，所以需要先做一次 Milvus 标量精确匹配。
IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/\\-]{3,}")
MAX_EXACT_TERMS = 5
_vector_store_manager: Any | None = None


@tool(response_format="content_and_artifact")
def retrieve_knowledge(query: str) -> Tuple[str, List[Document]]:
    """从知识库中检索相关信息来回答问题
    
    当用户的问题涉及专业知识、文档内容或需要参考资料时，使用此工具。
    
    Args:
        query: 用户的问题或查询
        
    Returns:
        Tuple[str, List[Document]]: (格式化的上下文文本, 原始文档列表)
    """
    try:
        logger.info(f"知识检索工具被调用: query='{query}'")

        # 优先做精确关键词检索。
        # 例如用户问 "OnCallUploadDemo20260618 是什么？" 时，
        # 向量模型可能不知道这个随机标识符的语义，但 Milvus content 字段里确实有这段原文。
        exact_docs = search_exact_keyword_documents(query, limit=config.rag_top_k)
        if exact_docs:
            context = format_docs(exact_docs)
            logger.info(f"精确关键词检索命中 {len(exact_docs)} 个文档")
            return context, exact_docs

        # 从向量存储中检索相关文档
        vector_store = get_vector_store_manager().get_vector_store()
        retriever = vector_store.as_retriever(
            search_kwargs={"k": config.rag_top_k}
        )
        
        docs = retriever.invoke(query)
        
        if not docs:
            logger.warning("未检索到相关文档")
            return "没有找到相关信息。", []
        
        # 格式化文档为上下文
        context = format_docs(docs)
        
        logger.info(f"检索到 {len(docs)} 个相关文档")
        return context, docs
        
    except Exception as e:
        logger.error(f"知识检索工具调用失败: {e}")
        return f"检索知识时发生错误: {str(e)}", []


def search_exact_keyword_documents(query: str, limit: int = 3) -> List[Document]:
    """
    根据问题中的精确标识符从 Milvus content 字段查找文档。

    适用场景：
    - 用户问上传文件中的唯一测试词，如 OnCallUploadDemo20260618
    - 用户问服务名、告警名、文件名、英文/数字混合编号

    Args:
        query: 用户问题
        limit: 最多返回的文档数量

    Returns:
        List[Document]: 精确命中的文档列表
    """
    terms = extract_identifier_terms(query)
    if not terms:
        return []

    try:
        collection = milvus_manager.get_collection()
    except Exception as exc:
        logger.warning(f"Milvus collection 不可用，跳过精确关键词检索: {exc}")
        return []

    docs: List[Document] = []
    seen_ids: set[str] = set()

    for term in terms:
        if len(docs) >= limit:
            break

        escaped_term = escape_milvus_string(term)
        expr = f'content like "%{escaped_term}%"'

        try:
            rows = collection.query(
                expr=expr,
                output_fields=["id", "content", "metadata"],
                limit=limit,
            )
        except Exception as exc:
            logger.warning(f"精确关键词检索失败: term='{term}', error={exc}")
            continue

        rows = sort_exact_rows_by_term(rows, term)

        for row in rows:
            doc_id = str(row.get("id", ""))
            if doc_id and doc_id in seen_ids:
                continue

            content = row.get("content") or ""
            metadata = normalize_metadata(row.get("metadata"))
            metadata["_milvus_id"] = doc_id
            metadata["_match_type"] = "exact_keyword"
            metadata["_matched_term"] = term

            docs.append(Document(page_content=content, metadata=metadata))
            if doc_id:
                seen_ids.add(doc_id)

            if len(docs) >= limit:
                break

    return docs


def get_vector_store_manager() -> Any:
    """懒加载向量库管理器，避免导入工具包时强制连接 Milvus。"""
    global _vector_store_manager
    if _vector_store_manager is None:
        from app.services.vector_store_manager import vector_store_manager

        _vector_store_manager = vector_store_manager
    return _vector_store_manager


def extract_identifier_terms(query: str) -> List[str]:
    """
    从用户问题里提取适合做精确匹配的标识符。

    这里故意只提取英文/数字/符号组成的较长词，避免把普通中文问题都拿去做
    LIKE 查询，导致召回过宽或性能浪费。
    """
    terms: List[str] = []

    for match in IDENTIFIER_PATTERN.finditer(query):
        term = match.group(0).strip(".,;:!?，。；：！？()（）[]【】'\"")
        if len(term) < 4:
            continue
        if term not in terms:
            terms.append(term)
        if len(terms) >= MAX_EXACT_TERMS:
            break

    return terms


def escape_milvus_string(value: str) -> str:
    """转义用于 Milvus 表达式字符串字面量的字符。"""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def normalize_metadata(metadata: Any) -> Dict[str, Any]:
    """确保 Milvus JSON metadata 字段以字典形式进入 LangChain Document。"""
    if isinstance(metadata, dict):
        return dict(metadata)
    return {}


def sort_exact_rows_by_term(rows: List[Dict[str, Any]], term: str) -> List[Dict[str, Any]]:
    """
    将关键词出现位置更靠前的 chunk 排在前面。

    用户问“某个标识符是什么”时，标题/文档信息 chunk 通常会把关键词放在前部；
    排在前面后，大模型更容易先读到定义性信息。
    """
    term_lower = term.lower()

    def sort_key(row: Dict[str, Any]) -> int:
        content = str(row.get("content") or "").lower()
        position = content.find(term_lower)
        if position == -1:
            return 10_000_000
        return position

    return sorted(rows, key=sort_key)


def format_docs(docs: List[Document]) -> str:
    """
    格式化文档列表为上下文文本
    
    Args:
        docs: 文档列表
        
    Returns:
        str: 格式化的上下文文本
    """
    formatted_parts = []
    
    for i, doc in enumerate(docs, 1):
        # 提取元数据
        metadata = doc.metadata
        source = metadata.get("_file_name", "未知来源")
        
        # 提取标题信息 (如果有)
        headers = []
        for key in ["h1", "h2", "h3"]:
            if key in metadata and metadata[key]:
                headers.append(metadata[key])
        
        header_str = " > ".join(headers) if headers else ""
        
        # 构建格式化文本
        formatted = f"【参考资料 {i}】"
        if header_str:
            formatted += f"\n标题: {header_str}"
        formatted += f"\n来源: {source}"
        formatted += f"\n内容:\n{doc.page_content}\n"
        
        formatted_parts.append(formatted)
    
    return "\n".join(formatted_parts)
