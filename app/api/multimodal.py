"""多模态聊天接口。"""

from fastapi import APIRouter, File, Form, UploadFile
from loguru import logger

from app.services.aiops_memory_service import aiops_memory_service
from app.services.multimodal_understanding_service import (
    RawMultimodalUpload,
    multimodal_understanding_service,
)
from app.services.structured_memory_service import structured_memory_service

router = APIRouter()


@router.post("/chat_multimodal")
async def chat_multimodal(
    id: str = Form(..., alias="Id"),
    question: str = Form("", alias="Question"),
    tenant_id: str = Form("local", alias="TenantId"),
    user_id: str = Form("local_user", alias="UserId"),
    files: list[UploadFile] | None = File(default=None),
):
    """接收图片/截图/文本附件，让多模态模型理解后回答。"""
    try:
        uploads: list[RawMultimodalUpload] = []
        for file in files or []:
            content = await file.read()
            uploads.append(
                RawMultimodalUpload(
                    filename=file.filename or "attachment",
                    content_type=file.content_type,
                    content=content,
                )
            )

        attachment_names = [item.filename for item in uploads]
        logger.info(f"[会话 {id}] 收到多模态对话请求: {question}, 附件: {attachment_names}")

        result = multimodal_understanding_service.analyze(
            question=question,
            uploads=uploads,
        )
        answer = result["answer"]

        memory_user_message = question.strip() or "用户提交了多模态附件"
        if attachment_names:
            memory_user_message += "\n附件: " + "、".join(attachment_names)

        memory_capture = None
        preference_capture = []
        try:
            memory_capture = aiops_memory_service.capture_chat_followup(
                session_id=id,
                user_message=memory_user_message,
                assistant_answer=answer,
            )
            preference_capture = structured_memory_service.capture_user_preferences(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=id,
                user_message=memory_user_message,
            )
        except Exception as memory_error:
            logger.warning(f"[会话 {id}] 多模态对话记忆捕获失败，不影响回答: {memory_error}")

        logger.info(f"[会话 {id}] 多模态对话完成")

        return {
            "code": 200,
            "message": "success",
            "data": {
                "success": True,
                "answer": answer,
                "model": result["model"],
                "attachments": result["attachments"],
                "memoryCapture": memory_capture.__dict__ if memory_capture else None,
                "preferenceCapture": [item.__dict__ for item in preference_capture],
                "errorMessage": None,
            },
        }

    except ValueError as e:
        logger.warning(f"多模态对话参数错误: {e}")
        return {
            "code": 400,
            "message": "error",
            "data": {
                "success": False,
                "answer": None,
                "errorMessage": str(e),
            },
        }
    except Exception as e:
        logger.error(f"多模态对话接口错误: {e}")
        return {
            "code": 500,
            "message": "error",
            "data": {
                "success": False,
                "answer": None,
                "errorMessage": str(e),
            },
        }
