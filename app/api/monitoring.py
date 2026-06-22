"""实时监控接口"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger
from datetime import datetime
import psutil
import os

router = APIRouter()


@router.get("/monitoring/status")
async def get_system_status():
    """获取系统实时状态 - 用于监控面板

    Returns:
        系统各项指标的实时状态
    """
    try:
        # 进程信息
        process = psutil.Process(os.getpid())

        # 系统指标
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # 应用进程指标
        process_memory = process.memory_info()

        status_data = {
            "timestamp": datetime.now().isoformat(),
            "service": {
                "name": "SuperBizAgent",
                "pid": os.getpid(),
                "uptime_seconds": (datetime.now().timestamp() - process.create_time()),
                "status": "running"
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "percent": disk.percent
                }
            },
            "process": {
                "memory_mb": round(process_memory.rss / (1024**2), 2),
                "threads": process.num_threads()
            }
        }

        return JSONResponse(content={
            "code": 200,
            "message": "获取系统状态成功",
            "data": status_data
        })

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": f"获取系统状态失败: {str(e)}"
            }
        )


@router.get("/monitoring/errors")
async def get_recent_errors():
    """获取最近的错误日志

    Returns:
        最近的错误日志列表
    """
    try:
        # 读取今天的日志文件
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"logs/app_{today}.log"

        if not os.path.exists(log_file):
            return JSONResponse(content={
                "code": 200,
                "message": "暂无错误日志",
                "data": {"errors": []}
            })

        # 读取最后100行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines

        # 筛选ERROR级别的日志
        errors = []
        for line in recent_lines:
            if "ERROR" in line or "ALERT" in line:
                errors.append(line.strip())

        return JSONResponse(content={
            "code": 200,
            "message": f"找到 {len(errors)} 条错误日志",
            "data": {
                "errors": errors[-20:],  # 返回最近20条
                "total": len(errors)
            }
        })

    except Exception as e:
        logger.error(f"获取错误日志失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": f"获取错误日志失败: {str(e)}"
            }
        )
