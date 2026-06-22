"""全局错误处理中间件"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from app.utils.alerting import alert_notifier


async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器 - 捕获所有未处理的异常"""

    error_context = {
        "path": str(request.url),
        "method": request.method,
        "client": request.client.host if request.client else "unknown"
    }

    # 记录详细错误日志
    logger.error(
        f"未处理的异常: {type(exc).__name__}",
        exc_info=exc,
        extra=error_context
    )

    # 发送告警通知
    alert_notifier.notify_error(
        error_type=type(exc).__name__,
        message=str(exc),
        context=error_context
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": str(exc) if logger.level("DEBUG").no <= logger._core.min_level else None
        }
    )
