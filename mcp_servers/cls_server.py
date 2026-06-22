"""腾讯云 CLS (Cloud Log Service) MCP Server

本地实现的 CLS 日志服务 MCP Server，提供日志查询、检索和分析功能。
"""

import logging
import functools
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastmcp import FastMCP

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CLS_MCP_Server")

mcp = FastMCP("CLS")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file() -> None:
    """加载项目根目录下的 .env，避免独立启动 MCP 服务时读不到配置。"""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # 不覆盖系统环境变量，方便启动时临时指定配置。
        os.environ.setdefault(key, value)


load_env_file()


# ==================== 本地日志 CLS 配置 ====================
#
# 默认使用本地日志模式，直接读取 logs/app_YYYY-MM-DD.log。
# 如果以后要接真实腾讯云 CLS，可以把 CLS_LOG_MODE 改成 tencent，
# 然后在 search_log 中接入腾讯云 SDK。
CLS_LOG_MODE = os.getenv("CLS_LOG_MODE", "local").lower()
CLS_LOCAL_TOPIC_ID = os.getenv("CLS_LOCAL_TOPIC_ID", "local-app-logs")
CLS_LOCAL_TOPIC_NAME = os.getenv("CLS_LOCAL_TOPIC_NAME", "本地应用日志")
CLS_LOCAL_SERVICE_NAME = os.getenv("CLS_LOCAL_SERVICE_NAME", "super-biz-agent")
CLS_LOCAL_REGION_CODE = os.getenv("CLS_LOCAL_REGION_CODE", "local")
CLS_LOCAL_LOG_DIR_TEXT = os.getenv("CLS_LOCAL_LOG_DIR", "logs")
CLS_LOCAL_LOG_DIR = Path(CLS_LOCAL_LOG_DIR_TEXT)
if not CLS_LOCAL_LOG_DIR.is_absolute():
    CLS_LOCAL_LOG_DIR = PROJECT_ROOT / CLS_LOCAL_LOG_DIR

LOG_FILE_PATTERN = "app_*.log"
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+\|\s+(?P<level>[A-Z]+)\s+\|\s+"
    r"(?P<source>[^|]+)\s+\|\s+(?P<message>.*)$"
)


def log_tool_call(func):
    """装饰器：记录工具调用的日志，包括方法名、参数和返回状态"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        method_name = func.__name__

        # 记录调用信息
        logger.info(f"=" * 80)
        logger.info(f"调用方法: {method_name}")

        # 记录参数（排除self等）
        if kwargs:
            # 使用 json.dumps 格式化参数，处理可能的序列化错误
            try:
                params_str = json.dumps(kwargs, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                params_str = str(kwargs)
            logger.info(f"参数信息:\n{params_str}")
        else:
            logger.info("参数信息: 无")

        # 执行方法
        try:
            result = func(*args, **kwargs)

            # 记录返回状态
            logger.info(f"返回状态: SUCCESS")

            # 记录返回结果摘要（避免日志过长）
            if isinstance(result, dict):
                summary = {k: v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} with {len(v)} items>"
                          for k, v in list(result.items())[:5]}
                logger.info(f"返回结果摘要: {json.dumps(summary, ensure_ascii=False)}")
            else:
                logger.info(f"返回结果: {result}")

            logger.info(f"=" * 80)
            return result

        except Exception as e:
            # 记录错误状态
            logger.error(f"返回状态: ERROR")
            logger.error(f"错误信息: {str(e)}")
            logger.error(f"=" * 80)
            raise

    return wrapper


def parse_time_or_default(time_str: Optional[str], default_offset_hours: int = 0) -> datetime:
    """解析时间字符串或返回默认时间。

    Args:
        time_str: 时间字符串（格式：YYYY-MM-DD HH:MM:SS）
        default_offset_hours: 默认时间偏移（小时）

    Returns:
        datetime: 解析后的时间对象
    """
    if time_str:
        try:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now() + timedelta(hours=default_offset_hours)


def generate_time_series(base_time: datetime, minutes_offset: int) -> str:
    """生成基于基准时间的时间字符串。

    Args:
        base_time: 基准时间
        minutes_offset: 分钟偏移量

    Returns:
        str: 格式化的时间字符串
    """
    result_time = base_time + timedelta(minutes=minutes_offset)
    return result_time.strftime("%Y-%m-%d %H:%M:%S")


def get_local_topic(service_name: Optional[str] = None) -> Dict[str, Any]:
    """返回本地日志 topic 信息。

    本地开发环境通常没有真正的腾讯云 CLS topic。
    这里把项目 logs/app_*.log 映射成一个虚拟 topic，让 Agent 可以用同一套 search_log 工具查询。
    """
    return {
        "topic_id": CLS_LOCAL_TOPIC_ID,
        "topic_name": CLS_LOCAL_TOPIC_NAME,
        "service_name": service_name or CLS_LOCAL_SERVICE_NAME,
        "region_code": CLS_LOCAL_REGION_CODE,
        "create_time": "",
        "log_count": count_local_log_lines(),
        "description": f"本地日志目录: {CLS_LOCAL_LOG_DIR}",
        "source_type": "local_file",
    }


def count_local_log_lines() -> int:
    """统计本地日志总行数，仅用于 topic 信息展示。"""
    if not CLS_LOCAL_LOG_DIR.exists():
        return 0

    total = 0
    for log_file in CLS_LOCAL_LOG_DIR.glob(LOG_FILE_PATTERN):
        try:
            with log_file.open("r", encoding="utf-8", errors="ignore") as file:
                total += sum(1 for _ in file)
        except OSError:
            continue
    return total


def iter_log_files_by_time(start_time: int, end_time: int) -> list[Path]:
    """根据查询时间范围选择需要读取的日志文件。

    项目日志按天写入 logs/app_YYYY-MM-DD.log。
    查询最近 15 分钟时，只需要读当天文件；跨天查询时会读取多个日期文件。
    """
    if not CLS_LOCAL_LOG_DIR.exists():
        return []

    start_date = datetime.fromtimestamp(start_time / 1000).date()
    end_date = datetime.fromtimestamp(end_time / 1000).date()

    files: list[Path] = []
    current_date = start_date
    while current_date <= end_date:
        log_file = CLS_LOCAL_LOG_DIR / f"app_{current_date:%Y-%m-%d}.log"
        if log_file.exists():
            files.append(log_file)
        current_date += timedelta(days=1)

    return files


def parse_log_entry(line: str) -> Optional[Dict[str, Any]]:
    """解析一行 Loguru 文件日志。

    日志格式来自 app/utils/logger.py:
        2026-06-18 20:31:38 | INFO     | module.func:12 | message
    """
    match = LOG_LINE_PATTERN.match(line.rstrip("\n"))
    if not match:
        return None

    timestamp_text = match.group("timestamp")
    try:
        parsed_time = datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return {
        "timestamp": timestamp_text,
        "_datetime": parsed_time,
        "level": match.group("level").strip(),
        "source": match.group("source").strip(),
        "message": match.group("message").strip(),
        "raw": line.rstrip("\n"),
    }


def read_local_log_entries(log_files: list[Path]) -> list[Dict[str, Any]]:
    """读取本地日志文件，并把异常堆栈续行合并到上一条日志。"""
    entries: list[Dict[str, Any]] = []
    current_entry: Optional[Dict[str, Any]] = None

    for log_file in log_files:
        try:
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for line in lines:
            parsed = parse_log_entry(line)
            if parsed:
                if current_entry:
                    entries.append(current_entry)
                parsed["file_name"] = log_file.name
                current_entry = parsed
                continue

            # 异常堆栈通常不是以时间戳开头，把它拼到上一条日志里。
            if current_entry and line.strip():
                current_entry["message"] += "\n" + line
                current_entry["raw"] += "\n" + line

    if current_entry:
        entries.append(current_entry)

    return entries


def parse_query(query: Optional[str]) -> Dict[str, Any]:
    """解析简化版日志查询语句。

    支持示例:
        level:ERROR
        level=ERROR
        message:Milvus
        level:ERROR AND Milvus
        timeout OR exception
    """
    if not query:
        return {"level": None, "terms": [], "mode": "and"}

    query_text = query.strip()
    level = None

    level_match = re.search(r"\blevel\s*[:=]\s*`?\"?'?([A-Za-z]+)`?\"?'?", query_text)
    if level_match:
        level = level_match.group(1).upper()
        query_text = query_text[: level_match.start()] + query_text[level_match.end() :]

    mode = "or" if re.search(r"\bOR\b", query_text, flags=re.IGNORECASE) else "and"
    query_text = re.sub(r"\bAND\b|\bOR\b", " ", query_text, flags=re.IGNORECASE)
    query_text = re.sub(r"\b(message|msg)\s*[:=]", " ", query_text, flags=re.IGNORECASE)

    raw_terms = re.split(r"[\s,，]+", query_text)
    terms = [
        term.strip().strip("`\"'")
        for term in raw_terms
        if term.strip().strip("`\"'")
    ]

    return {"level": level, "terms": terms, "mode": mode}


def match_log_query(entry: Dict[str, Any], parsed_query: Dict[str, Any]) -> bool:
    """判断一条日志是否匹配查询条件。"""
    level = parsed_query["level"]
    if level and entry.get("level") != level:
        return False

    terms = parsed_query["terms"]
    if not terms:
        return True

    haystack = (
        f"{entry.get('timestamp', '')} {entry.get('level', '')} "
        f"{entry.get('source', '')} {entry.get('message', '')}"
    ).lower()

    if parsed_query["mode"] == "or":
        return any(term.lower() in haystack for term in terms)

    return all(term.lower() in haystack for term in terms)


def search_local_log(
    topic_id: str,
    start_time: int,
    end_time: int,
    query: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """查询本地 logs/app_*.log 文件。"""
    started_at = time.perf_counter()

    if topic_id != CLS_LOCAL_TOPIC_ID:
        return {
            "topic_id": topic_id,
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": limit,
            "total": 0,
            "logs": [],
            "took_ms": 0,
            "error": f"本地日志 topic 不存在: {topic_id}",
            "message": f"本地模式只支持 topic_id={CLS_LOCAL_TOPIC_ID}",
        }

    log_files = iter_log_files_by_time(start_time, end_time)
    parsed_query = parse_query(query)
    entries = read_local_log_entries(log_files)

    start_dt = datetime.fromtimestamp(start_time / 1000)
    end_dt = datetime.fromtimestamp(end_time / 1000)

    matched_logs: list[Dict[str, Any]] = []
    total = 0

    for entry in entries:
        entry_time = entry["_datetime"]
        if entry_time < start_dt or entry_time > end_dt:
            continue
        if not match_log_query(entry, parsed_query):
            continue

        total += 1
        if len(matched_logs) < limit:
            matched_logs.append(
                {
                    "timestamp": entry["timestamp"],
                    "level": entry["level"],
                    "source": entry["source"],
                    "message": entry["message"],
                    "file_name": entry.get("file_name", ""),
                }
            )

    took_ms = int((time.perf_counter() - started_at) * 1000)

    return {
        "topic_id": topic_id,
        "topic_name": CLS_LOCAL_TOPIC_NAME,
        "source_type": "local_file",
        "log_dir": str(CLS_LOCAL_LOG_DIR),
        "log_files": [str(path) for path in log_files],
        "start_time": start_time,
        "end_time": end_time,
        "query": query,
        "limit": limit,
        "total": total,
        "logs": matched_logs,
        "took_ms": took_ms,
        "message": f"成功查询本地日志，匹配 {total} 条，返回 {len(matched_logs)} 条",
    }


@mcp.tool()
@log_tool_call
def get_current_timestamp() -> int:
    """获取当前时间戳（以毫秒为单位）。
    
    此工具用于获取标准的毫秒时间戳，可用于：
    1. 作为 search_log 的 end_time 参数（查询到现在）
    2. 计算历史时间点作为 start_time 参数
    
    Returns:
        int: 当前时间戳（毫秒），例如: 1708012345000
    
    使用示例:
        # 获取当前时间
        current = get_current_timestamp()
        
        # 计算15分钟前的时间
        fifteen_min_ago = current - (15 * 60 * 1000)
        
        # 计算1小时前的时间
        one_hour_ago = current - (60 * 60 * 1000)
        
        # 用于搜索最近15分钟的日志
        search_log(
            topic_id="topic-001",
            start_time=fifteen_min_ago,
            end_time=current
        )
    """
    return int(datetime.now().timestamp() * 1000)


@mcp.tool()
@log_tool_call
def get_region_code_by_name(region_name: str) -> Dict[str, Any]:
    """根据地区名称搜索对应的地区参数。

    Args:
        region_name: 地区名称（如：北京、上海、广州等）

    Returns:
        Dict: 包含地区代码和相关信息的字典
            - region_code: 地区代码
            - region_name: 地区名称
            - available: 是否可用
    """
    # 模拟地区映射表（实际应该从配置或数据库读取）
    region_mapping = {
        "北京": {"region_code": "ap-beijing", "region_name": "北京", "available": True},
        "上海": {"region_code": "ap-shanghai", "region_name": "上海", "available": True},
        "广州": {"region_code": "ap-guangzhou", "region_name": "广州", "available": True},
    }

    result = region_mapping.get(region_name)
    if result:
        return result
    else:
        return {
            "region_code": None,
            "region_name": region_name,
            "available": False,
            "error": f"未找到地区: {region_name}"
        }


@mcp.tool()
@log_tool_call
def get_topic_info_by_name(topic_name: str, region_code: Optional[str] = None) -> Dict[str, Any]:
    """根据主题名称搜索相关的主题信息。

    Args:
        topic_name: 主题名称
        region_code: 地区代码（可选）

    Returns:
        Dict: 包含主题信息的字典
            - topic_id: 主题ID
            - topic_name: 主题名称
            - region_code: 所属地区
            - create_time: 创建时间
            - log_count: 日志数量
    """
    if CLS_LOG_MODE == "local":
        topic_keywords = {
            CLS_LOCAL_TOPIC_ID.lower(),
            CLS_LOCAL_TOPIC_NAME.lower(),
            "local",
            "本地日志",
            "应用日志",
            "app",
        }
        if topic_name.lower() in topic_keywords or topic_name in CLS_LOCAL_TOPIC_NAME:
            return get_local_topic()

    mock_topics = [
        {
            "topic_id": "topic-001",
            "topic_name": "数据同步服务日志",
            "service_name": "data-sync-service",
            "region_code": "ap-beijing",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "服务应用日志"
        }
    ]

    # 根据名称和地区筛选
    for topic in mock_topics:
        if topic["topic_name"] == topic_name:
            if region_code is None or topic["region_code"] == region_code:
                return topic

    return {
        "topic_id": None,
        "topic_name": topic_name,
        "region_code": region_code,
        "error": f"未找到主题: {topic_name}"
    }


@mcp.tool()
@log_tool_call
def search_topic_by_service_name(
    service_name: str,
    region_code: Optional[str] = None,
    fuzzy: bool = True
) -> Dict[str, Any]:
    """根据服务名称搜索相关的日志主题信息，支持模糊搜索。
    
    此工具用于根据服务名称查找对应的日志主题（topic），便于后续进行日志查询。
    
    Args:
        service_name: 服务名称（必填）
            示例: "data-sync-service", "sync", "data-sync"
            说明: 当 fuzzy=True 时，支持部分匹配
        
        region_code: 地区代码（可选）
            示例: "ap-beijing", "ap-shanghai"
            说明: 如果指定，只返回该地区的主题
        
        fuzzy: 是否启用模糊搜索（可选，默认 True）
            True: 部分匹配，例如 "sync" 可以匹配 "data-sync-service"
            False: 精确匹配，必须完全一致
    
    Returns:
        Dict: 搜索结果
            - total: 匹配到的主题数量
            - topics: 主题列表，每个主题包含:
                * topic_id: 主题ID（用于后续日志查询）
                * topic_name: 主题名称
                * service_name: 服务名称
                * region_code: 所属地区
                * create_time: 创建时间
                * log_count: 日志数量
                * description: 主题描述
            - query: 查询条件
    
    使用示例:
        # 示例1: 模糊搜索（推荐）
        search_topic_by_service_name(service_name="data-sync")
        # 可以匹配: "data-sync-service", "data-sync-worker" 等
        
        # 示例2: 精确搜索
        search_topic_by_service_name(
            service_name="data-sync-service",
            fuzzy=False
        )
        
        # 示例3: 指定地区搜索
        search_topic_by_service_name(
            service_name="sync",
            region_code="ap-beijing"
        )
        
        # 示例4: 查找后进行日志搜索的完整流程
        # 步骤1: 根据服务名查找 topic
        result = search_topic_by_service_name(service_name="data-sync-service")
        
        # 步骤2: 获取 topic_id
        topic_id = result["topics"][0]["topic_id"]  # "topic-001"
        
        # 步骤3: 使用 topic_id 查询日志
        current_ts = get_current_timestamp()
        start_ts = current_ts - (15 * 60 * 1000)
        search_log(
            topic_id=topic_id,
            start_time=start_ts,
            end_time=current_ts
        )
    """
    if CLS_LOG_MODE == "local":
        local_topic = get_local_topic(service_name=service_name)
        return {
            "total": 1,
            "topics": [local_topic],
            "query": {
                "service_name": service_name,
                "region_code": region_code,
                "fuzzy": fuzzy,
                "mode": "local_file",
            },
            "message": (
                f"本地日志模式: 服务 '{service_name}' 映射到本地日志 topic "
                f"'{CLS_LOCAL_TOPIC_ID}'"
            ),
        }

    # Mock 主题数据（实际应该从配置或数据库读取）
    mock_topics = [
        {
            "topic_id": "topic-001",
            "topic_name": "数据同步服务日志",
            "service_name": "data-sync-service",
            "region_code": "ap-beijing",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "数据同步服务的应用日志，包含同步任务执行情况"
        },
        {
            "topic_id": "topic-002",
            "topic_name": "数据同步服务错误日志",
            "service_name": "data-sync-service",
            "region_code": "ap-beijing",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "数据同步服务的错误日志"
        },
        {
            "topic_id": "topic-003",
            "topic_name": "API网关服务日志",
            "service_name": "api-gateway-service",
            "region_code": "ap-shanghai",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "API网关服务日志"
        }
    ]
    
    matched_topics = []
    
    # 搜索逻辑
    for topic in mock_topics:
        # 地区筛选
        if region_code and topic["region_code"] != region_code:
            continue
        
        # 服务名称匹配
        topic_service_name = topic.get("service_name", "")
        
        if fuzzy:
            # 模糊匹配：服务名包含查询字符串，或查询字符串包含服务名
            if (service_name.lower() in topic_service_name.lower() or 
                topic_service_name.lower() in service_name.lower()):
                matched_topics.append(topic)
        else:
            # 精确匹配
            if topic_service_name == service_name:
                matched_topics.append(topic)
    
    return {
        "total": len(matched_topics),
        "topics": matched_topics,
        "query": {
            "service_name": service_name,
            "region_code": region_code,
            "fuzzy": fuzzy
        },
        "message": f"找到 {len(matched_topics)} 个匹配的日志主题" if matched_topics else f"未找到服务 '{service_name}' 的日志主题"
    }


@mcp.tool()
@log_tool_call
def list_local_log_files() -> Dict[str, Any]:
    """列出当前本地 CLS 可以读取的日志文件。

    此工具用于检查本地日志配置是否正确。
    如果 files 为空，请确认:
        1. 主程序已经运行并生成 logs/app_YYYY-MM-DD.log；
        2. .env 中 CLS_LOCAL_LOG_DIR 指向正确目录。
    """
    files = []
    if CLS_LOCAL_LOG_DIR.exists():
        for log_file in sorted(CLS_LOCAL_LOG_DIR.glob(LOG_FILE_PATTERN)):
            stat = log_file.stat()
            files.append(
                {
                    "file_name": log_file.name,
                    "path": str(log_file),
                    "size": stat.st_size,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )

    return {
        "mode": CLS_LOG_MODE,
        "topic_id": CLS_LOCAL_TOPIC_ID,
        "log_dir": str(CLS_LOCAL_LOG_DIR),
        "total": len(files),
        "files": files,
    }


@mcp.tool()
@log_tool_call
def search_log(
    topic_id: str,
    start_time: int,
    end_time: int,
    query: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """基于提供的查询参数搜索日志。

    Args:
        topic_id: 主题ID（必填）
            示例: "topic-001"
        
        start_time: 开始时间戳，单位为毫秒（必填，int类型）
            重要: 必须传递整数类型的毫秒时间戳
            获取方式: 
            1. 使用 get_current_timestamp() 工具获取当前时间戳
            2. 计算历史时间: current_timestamp - (分钟数 * 60 * 1000)
            示例: 
            - 当前时间: 1708012345000
            - 15分钟前: 1708012345000 - (15 * 60 * 1000) = 1708011445000
            - 1小时前: 1708012345000 - (60 * 60 * 1000) = 1708008745000
        
        end_time: 结束时间戳，单位为毫秒（必填，int类型）
            重要: 必须传递整数类型的毫秒时间戳
            通常使用 get_current_timestamp() 工具获取当前时间作为结束时间
            示例: 1708012345000
        
        query: 查询语句（可选，CLS 查询语法）
            示例: "level:ERROR" 或 "message:异常"
        
        limit: 返回结果数量限制（默认100，可选）

    Returns:
        Dict: 搜索结果
            - topic_id: 主题ID
            - start_time: 开始时间戳
            - end_time: 结束时间戳
            - query: 查询语句
            - limit: 结果限制
            - total: 实际返回的日志条数
            - logs: 日志列表，每条日志包含:
                * timestamp: 日志时间（格式: YYYY-MM-DD HH:MM:SS）
                * level: 日志级别
                * message: 日志内容
            - took_ms: 查询耗时（毫秒）
            - message: 查询状态消息
    
    使用示例:
        # 步骤1: 获取当前时间戳
        current_ts = get_current_timestamp()  # 返回: 1708012345000
        
        # 步骤2: 计算开始时间（15分钟前）
        start_ts = current_ts - (15 * 60 * 1000)  # 1708011445000
        
        # 步骤3: 搜索日志
        search_log(
            topic_id="topic-001",
            start_time=start_ts,     # int类型: 1708011445000
            end_time=current_ts,     # int类型: 1708012345000
            limit=100
        )
    """
    if CLS_LOG_MODE == "local":
        return search_local_log(
            topic_id=topic_id,
            start_time=start_time,
            end_time=end_time,
            query=query,
            limit=limit,
        )

    # 根据 topic_id 返回不同的结果
    if topic_id == "topic-001":
        # topic-001: 应用日志，动态生成 INFO 日志
        logs = []
        current_time_ms = start_time
        count = 0

        # 计算最大可生成的日志条数（基于时间范围）
        max_logs_by_time = int((end_time - start_time) / (60 * 1000)) + 1

        # 实际生成的日志数量取 limit 和时间范围内最大日志数的较小值
        actual_limit = min(limit, max_logs_by_time)

        while current_time_ms <= end_time and count < actual_limit:
            # 将毫秒时间戳转换为可读格式
            log_time = datetime.fromtimestamp(current_time_ms / 1000)
            time_str = log_time.strftime("%Y-%m-%d %H:%M:%S")

            log_entry = {
                "timestamp": time_str,
                "level": "INFO",
                "message": "正在同步元数据……"
            }

            logs.append(log_entry)
            count += 1

            # 下一条日志时间增加1分钟（60秒 * 1000毫秒）
            current_time_ms += 60 * 1000

        return {
            "topic_id": topic_id,
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": limit,
            "total": len(logs),
            "logs": logs,
            "took_ms": 50,
            "message": f"成功查询 {len(logs)} 条应用日志"
        }
    else:
        # 其他 topic_id: 返回错误，表示 topic 不存在
        return {
            "topic_id": topic_id,
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": limit,
            "total": 0,
            "logs": [],
            "took_ms": 0,
            "error": f"主题不存在: {topic_id}",
            "message": f"错误: 未找到主题 {topic_id}，请检查 topic_id 是否正确"
        }



if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8003, path="/mcp")
