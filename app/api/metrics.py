"""Prometheus 指标暴露接口。

Prometheus 会定时访问 /metrics，把这里返回的指标采集到自己的时序数据库中。
"""

from __future__ import annotations

import os
from datetime import datetime

import psutil
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest


router = APIRouter()


SYSTEM_CPU_PERCENT = Gauge(
    "super_biz_agent_system_cpu_percent",
    "Current system CPU usage percent.",
)
SYSTEM_MEMORY_PERCENT = Gauge(
    "super_biz_agent_system_memory_percent",
    "Current system memory usage percent.",
)
SYSTEM_DISK_PERCENT = Gauge(
    "super_biz_agent_system_disk_percent",
    "Current system disk usage percent.",
)
PROCESS_MEMORY_MB = Gauge(
    "super_biz_agent_process_memory_mb",
    "Current SuperBizAgent process RSS memory in MB.",
)
PROCESS_THREADS = Gauge(
    "super_biz_agent_process_threads",
    "Current SuperBizAgent process thread count.",
)
PROCESS_UPTIME_SECONDS = Gauge(
    "super_biz_agent_process_uptime_seconds",
    "Current SuperBizAgent process uptime in seconds.",
)


def update_runtime_metrics() -> None:
    """在 Prometheus 每次 scrape 时刷新本机和进程指标。"""
    process = psutil.Process(os.getpid())
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    process_memory = process.memory_info()

    SYSTEM_CPU_PERCENT.set(psutil.cpu_percent(interval=None))
    SYSTEM_MEMORY_PERCENT.set(memory.percent)
    SYSTEM_DISK_PERCENT.set(disk.percent)
    PROCESS_MEMORY_MB.set(round(process_memory.rss / (1024**2), 2))
    PROCESS_THREADS.set(process.num_threads())
    PROCESS_UPTIME_SECONDS.set(datetime.now().timestamp() - process.create_time())


@router.get("/metrics")
async def metrics() -> Response:
    """返回 Prometheus 文本格式指标。"""
    update_runtime_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
