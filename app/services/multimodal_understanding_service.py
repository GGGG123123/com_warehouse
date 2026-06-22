"""多模态输入理解服务。

这个服务用于处理聊天框里随问题一起提交的附件：
- 图片/截图：转为 data URL，交给支持视觉理解的多模态模型。
- 文本类文件：读取为文本片段，和用户问题一起交给模型。

它不负责把文件写入知识库，也不负责 Milvus 入库；知识库上传仍然走原来的
`/api/upload` 接口。
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory


IMAGE_MIME_PREFIX = "image/"
SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".log",
    ".json",
    ".jsonl",
    ".csv",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".py",
    ".sql",
    ".ini",
    ".conf",
}


@dataclass(frozen=True)
class RawMultimodalUpload:
    """API 层传给服务层的原始附件。"""

    filename: str
    content_type: str | None
    content: bytes


@dataclass(frozen=True)
class PreparedAttachment:
    """已经整理好、可以放进模型提示词或消息体的附件。"""

    name: str
    mime_type: str
    kind: str
    size: int
    text: str | None = None
    data_url: str | None = None


class MultimodalUnderstandingService:
    """把图片、截图、文本附件交给多模态模型理解。"""

    def analyze(
        self,
        question: str,
        uploads: list[RawMultimodalUpload],
    ) -> dict[str, Any]:
        """分析用户问题和附件，并返回模型回答。

        Args:
            question: 用户在输入框里写的问题，可以为空。
            uploads: 用户本轮选择或粘贴的附件。

        Returns:
            包含 answer 和 attachments 元信息的字典。
        """
        prepared = [self.prepare_attachment(upload) for upload in uploads]
        if not prepared:
            raise ValueError("请至少添加一个图片、截图或文本类文件")

        text_parts = self.build_text_parts(question, prepared)
        image_parts = [
            {
                "type": "image_url",
                "image_url": {"url": item.data_url},
            }
            for item in prepared
            if item.kind == "image" and item.data_url
        ]

        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": "\n\n".join(text_parts),
            }
        ]
        user_content.extend(image_parts)

        llm = llm_factory.create_chat_model(
            model=config.multimodal_model,
            temperature=0.2,
            streaming=False,
        )
        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "你是智能 OnCall 助手，擅长理解监控截图、报错截图、日志截图、"
                        "Markdown 文档和文本文件。回答时先说明你从附件中看到了什么，"
                        "再给出可能原因、排查步骤和可执行建议。不要编造附件中没有的事实。"
                    )
                ),
                HumanMessage(content=user_content),
            ]
        )

        answer = response.content
        if not isinstance(answer, str):
            answer = str(answer)

        return {
            "answer": answer,
            "model": config.multimodal_model,
            "attachments": [
                {
                    "name": item.name,
                    "mimeType": item.mime_type,
                    "kind": item.kind,
                    "size": item.size,
                }
                for item in prepared
            ],
        }

    def prepare_attachment(self, upload: RawMultimodalUpload) -> PreparedAttachment:
        """把一个上传附件整理为图片 data URL 或文本片段。"""
        filename = upload.filename or "attachment"
        size = len(upload.content)
        if size == 0:
            raise ValueError(f"附件为空: {filename}")
        if size > config.multimodal_max_file_bytes:
            max_mb = config.multimodal_max_file_bytes / 1024 / 1024
            raise ValueError(f"附件过大: {filename}，最大支持 {max_mb:.0f}MB")

        mime_type = self.detect_mime_type(filename, upload.content_type)
        extension = Path(filename).suffix.lower()

        if mime_type.startswith(IMAGE_MIME_PREFIX):
            data_url = self.build_data_url(mime_type, upload.content)
            return PreparedAttachment(
                name=filename,
                mime_type=mime_type,
                kind="image",
                size=size,
                data_url=data_url,
            )

        if extension in SUPPORTED_TEXT_EXTENSIONS or mime_type.startswith("text/"):
            text = self.decode_text(upload.content)
            if len(text) > config.multimodal_max_text_chars:
                text = text[: config.multimodal_max_text_chars] + "\n\n[内容过长，已截断]"
            return PreparedAttachment(
                name=filename,
                mime_type=mime_type,
                kind="text",
                size=size,
                text=text,
            )

        raise ValueError(
            f"暂不支持该附件类型: {filename}。请使用图片、截图或常见文本类文件。"
        )

    def build_text_parts(
        self,
        question: str,
        prepared: list[PreparedAttachment],
    ) -> list[str]:
        """构造给多模态模型的文本提示内容。"""
        cleaned_question = question.strip()
        if not cleaned_question:
            cleaned_question = "请理解这些附件，提取关键信息并给出运维分析建议。"

        attachment_summary = "\n".join(
            f"- {item.name} ({item.kind}, {item.mime_type}, {item.size} bytes)"
            for item in prepared
        )

        text_parts = [
            f"用户问题:\n{cleaned_question}",
            f"附件列表:\n{attachment_summary}",
        ]

        for item in prepared:
            if item.kind == "text" and item.text:
                text_parts.append(f"文本附件 {item.name} 内容:\n```text\n{item.text}\n```")

        return text_parts

    @staticmethod
    def detect_mime_type(filename: str, content_type: str | None) -> str:
        """优先使用浏览器上传的 MIME 类型，缺失时按文件名推断。"""
        if content_type and content_type != "application/octet-stream":
            return content_type
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or "application/octet-stream"

    @staticmethod
    def build_data_url(mime_type: str, content: bytes) -> str:
        """把图片二进制内容转成 OpenAI 兼容消息支持的 data URL。"""
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def decode_text(content: bytes) -> str:
        """尽量兼容 UTF-8 和常见中文 Windows 编码。"""
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue

        logger.warning("文本附件编码无法识别，使用替换模式解码")
        return content.decode("utf-8", errors="replace")


multimodal_understanding_service = MultimodalUnderstandingService()
