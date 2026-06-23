"""向量嵌入服务模块 - 基于 LangChain Embeddings 标准接口"""

from typing import List

from langchain_core.embeddings import Embeddings
from openai import OpenAI as CompatibleClient
from loguru import logger

from app.config import config


class CompatibleEmbeddings(Embeddings):
    """兼容模式 Text Embedding
    
    实现 LangChain 标准 Embeddings 接口:
    - embed_documents(texts: List[str]) → List[List[float]]: 批量嵌入文档
    - embed_query(text: str) → List[float]: 嵌入单个查询
    """

    # 当前 embedding 服务限制单次 input.contents 不能超过 10 条。
    # 在服务内部兜底拆批，避免调用方一次传入过多文档时报 400。
    MAX_DOCUMENT_BATCH_SIZE = 10

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        dimensions: int = 1024,
    ):
        """
        初始化 Embeddings
        
        Args:
            api_key: Embedding API Key
            model: 嵌入模型名称
            dimensions: 向量维度
        """
        if not api_key or "replace_with" in api_key:
            raise ValueError("请设置环境变量 MODEL_API_KEY")
        if not base_url or "replace_with" in base_url:
            raise ValueError("请设置环境变量 MODEL_API_BASE")
        
        self.client = CompatibleClient(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.dimensions = dimensions
        
        # 打印初始化信息
        masked_key = self._mask_api_key(api_key)
        logger.info(
            f"Embeddings 初始化完成 - "
            f"模型: {model}, 维度: {dimensions}, API Key: {masked_key}"
        )

    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        """掩码 API Key 用于日志"""
        if len(api_key) > 8:
            return f"{api_key[:8]}...{api_key[-4:]}"
        return "***"

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量嵌入文档列表 (LangChain 标准接口)
        
        Args:
            texts: 文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        if not texts:
            return []
        
        try:
            logger.info(f"批量嵌入 {len(texts)} 个文档")

            embeddings: List[List[float]] = []
            total_batches = (
                len(texts) + self.MAX_DOCUMENT_BATCH_SIZE - 1
            ) // self.MAX_DOCUMENT_BATCH_SIZE

            for batch_index, start in enumerate(
                range(0, len(texts), self.MAX_DOCUMENT_BATCH_SIZE),
                start=1,
            ):
                batch_texts = texts[start : start + self.MAX_DOCUMENT_BATCH_SIZE]
                logger.debug(
                    f"嵌入批次 {batch_index}/{total_batches}, "
                    f"本批 {len(batch_texts)} 个文档"
                )

                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch_texts,
                    dimensions=self.dimensions,
                    encoding_format="float"
                )

                embeddings.extend(item.embedding for item in response.data)

            logger.debug(f"批量嵌入完成, 维度: {len(embeddings[0])}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"批量嵌入失败: {e}")
            raise RuntimeError(f"批量嵌入失败: {e}") from e

    def embed_query(self, text: str) -> List[float]:
        """
        嵌入单个查询文本 (LangChain 标准接口)
        
        Args:
            text: 查询文本
            
        Returns:
            List[float]: 嵌入向量
        """
        if not text or not text.strip():
            raise ValueError("查询文本不能为空")
        
        try:
            logger.debug(f"嵌入查询, 长度: {len(text)} 字符")
            
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"查询嵌入完成, 维度: {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"查询嵌入失败: {e}")
            raise RuntimeError(f"查询嵌入失败: {e}") from e


# 全局单例
vector_embedding_service = CompatibleEmbeddings(
    api_key=config.model_api_key,
    model=config.embedding_model,
    base_url=config.model_api_base,
    dimensions=1024
)
