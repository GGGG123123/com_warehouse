"""
AIOps Agent 通用工具函数
"""

from typing import Any, Dict, List

from .state import PlanExecuteState


MAX_NODE_RETRIES = 2


def format_tools_description(tools: List) -> str:
    """格式化工具列表为描述文本"""
    tool_descriptions = []
    for tool in tools:
        if hasattr(tool, 'name') and hasattr(tool, 'description'):
            tool_descriptions.append(f"- {tool.name}: {tool.description}")
    return "\n".join(tool_descriptions)


def build_retry_update(
    state: PlanExecuteState,
    node_name: str,
    error: BaseException,
    max_retries: int = MAX_NODE_RETRIES,
) -> Dict[str, Any]:
    """记录节点失败并返回路由回当前节点所需的状态更新。

    max_retries 表示失败后的额外重试次数，不包含第一次正常尝试。
    """
    retry_counts = dict(state.get("retry_counts", {}))
    current_retries = retry_counts.get(node_name, 0)

    if current_retries >= max_retries:
        retry_counts.pop(node_name, None)
        return {
            "retry_counts": retry_counts,
            "retrying_node": "",
            "retry_attempt": 0,
            "retry_error": str(error),
            "retry_exhausted_node": node_name,
        }

    next_retry = current_retries + 1
    retry_counts[node_name] = next_retry
    return {
        "retry_counts": retry_counts,
        "retrying_node": node_name,
        "retry_attempt": next_retry,
        "retry_error": str(error),
        "retry_exhausted_node": "",
    }


def clear_retry_update(state: PlanExecuteState, node_name: str) -> Dict[str, Any]:
    """清理某个节点的重试状态，通常在节点成功或完成降级后调用。"""
    retry_counts = dict(state.get("retry_counts", {}))
    retry_counts.pop(node_name, None)
    return {
        "retry_counts": retry_counts,
        "retrying_node": "",
        "retry_attempt": 0,
        "retry_error": "",
        "retry_exhausted_node": "",
    }
