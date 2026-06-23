"""LLM 工厂类

使用兼容模式调用可配置的大模型服务。
这种方式便于后续切换到其他兼容模型提供商。

只需修改 base_url 和 api_key 即可切换兼容服务。
"""

from langchain_openai import ChatOpenAI
from app.config import config
from loguru import logger


class LLMFactory:
    """LLM 工厂类 - 使用兼容模式"""

    @staticmethod
    def create_chat_model(
        model: str | None = None,
        temperature: float = 0.7,
        streaming: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> ChatOpenAI:
        model = model or config.model_name
        base_url = base_url or config.model_api_base
        api_key = api_key or config.model_api_key

        if not api_key or "replace_with" in api_key:
            raise ValueError("请设置环境变量 MODEL_API_KEY")
        if not base_url or "replace_with" in base_url:
            raise ValueError("请设置环境变量 MODEL_API_BASE")

        extra_body = {}
        extra_body["stream"] = streaming

        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
            base_url=base_url,
            api_key=api_key,
            extra_body=extra_body if extra_body else None,
        )

        return llm

# 全局 LLM 工厂实例
llm_factory = LLMFactory()
