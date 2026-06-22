"""请求数据模型

定义 API 请求的 Pydantic 模型
"""

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""

    id: str = Field(..., description="会话 ID", alias="Id")
    question: str = Field(..., description="用户问题", alias="Question")
    tenant_id: Optional[str] = Field(default="local", description="租户/团队 ID", alias="TenantId")
    user_id: Optional[str] = Field(default="local_user", description="用户 ID", alias="UserId")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "Id": "session-123",
                "Question": "什么是向量数据库？",
                "TenantId": "local",
                "UserId": "local_user"
            }
        }


class ClearRequest(BaseModel):
    """清空会话请求"""

    session_id: str = Field(..., description="会话 ID", alias="sessionId")

    class Config:
        populate_by_name = True
