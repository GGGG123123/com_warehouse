"""配置管理模块

使用 Pydantic Settings 实现类型安全的配置管理
"""

from typing import Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "SuperBizAgent"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9900

    # 大模型服务配置
    model_api_key: str = ""
    model_api_base: str = ""
    model_name: str = "replace_with_your_chat_model"
    embedding_model: str = "replace_with_your_embedding_model"

    # Milvus 配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_timeout: int = 10000  # 毫秒

    # RAG 配置
    rag_top_k: int = 3
    rag_model: str = "replace_with_your_rag_model"

    # 多模态输入配置
    # 用于理解用户本轮输入里的图片、截图、日志/Markdown 等附件。
    multimodal_model: str = "replace_with_your_multimodal_model"
    multimodal_max_file_bytes: int = 10 * 1024 * 1024
    multimodal_max_text_chars: int = 12000

    # 长期记忆评估模型配置
    # 这个模型专门判断“是否值得存入长期记忆”和生成记忆摘要，和主聊天模型分开。
    memory_evaluator_enabled: bool = True
    memory_evaluator_model: str = "deepseek-v4-flash"
    memory_evaluator_store_threshold: float = 0.65
    memory_case_duplicate_similarity: float = 0.88
    memory_procedure_duplicate_similarity: float = 0.90
    memory_followup_duplicate_similarity: float = 0.86

    # 文档分块配置
    chunk_max_size: int = 800
    chunk_overlap: int = 100

    # MCP 服务配置（transport: stdio | sse | streamable-http）
    # 托管 MCP 的 URL 通常含 /sse/，需使用 sse；本地 FastMCP 使用 streamable-http
    mcp_cls_transport: str = "streamable-http"
    mcp_cls_url: str = "http://localhost:8003/mcp"
    mcp_monitor_transport: str = "streamable-http"
    mcp_monitor_url: str = "http://localhost:8004/mcp"

    # Prometheus
    prometheus_base_url: str = "http://127.0.0.1:9090"
    prometheus_request_timeout: float = 10.0

    @property
    def mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        """获取完整的 MCP 服务器配置"""
        return {
            "cls": {
                "transport": self.mcp_cls_transport,
                "url": self.mcp_cls_url,
            },
            "monitor": {
                "transport": self.mcp_monitor_transport,
                "url": self.mcp_monitor_url,
            }
        }


# 全局配置实例
config = Settings()
