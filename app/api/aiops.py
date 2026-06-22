"""
AIOps 智能运维接口
"""

import json
from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from app.models.aiops import AIOpsRequest
from app.services.aiops_memory_service import aiops_memory_service
from app.services.aiops_service import aiops_service

router = APIRouter()


@router.post("/aiops")
async def diagnose_stream(request: AIOpsRequest):
    """
    AIOps 故障诊断接口（流式 SSE）

    **功能说明：**
    - 自动获取当前系统的活动告警
    - 使用 Plan-Execute-Replan 模式进行智能诊断
    - 流式返回诊断过程和结果

    **SSE 事件类型：**

    1. `status` - 状态更新
       ```json
       {
         "type": "status",
         "stage": "fetching_alerts",
         "message": "正在获取系统告警信息..."
       }
       ```

    2. `plan` - 诊断计划制定完成
       ```json
       {
         "type": "plan",
         "stage": "plan_created",
         "message": "诊断计划已制定，共 6 个步骤",
         "target_alert": {...},
         "plan": ["步骤1: ...", "步骤2: ..."]
       }
       ```

    3. `step_complete` - 步骤执行完成
       ```json
       {
         "type": "step_complete",
         "stage": "step_executed",
         "message": "步骤执行完成 (2/6)",
         "current_step": "查询系统日志",
         "result_preview": "...",
         "remaining_steps": 4
       }
       ```

    4. `report` - 最终诊断报告
       ```json
       {
         "type": "report",
         "stage": "final_report",
         "message": "最终诊断报告已生成",
         "report": "# 故障诊断报告\\n...",
         "evidence": {...}
       }
       ```

    5. `complete` - 诊断完成
       ```json
       {
         "type": "complete",
         "stage": "diagnosis_complete",
         "message": "诊断流程完成",
         "diagnosis": {...}
       }
       ```

    6. `error` - 错误信息
       ```json
       {
         "type": "error",
         "stage": "error",
         "message": "诊断过程发生错误: ..."
       }
       ```

    **使用示例：**
    ```bash
    curl -X POST "http://localhost:9900/api/aiops" \\
      -H "Content-Type: application/json" \\
      -d '{"session_id": "session-123"}' \\
      --no-buffer
    ```

    **前端使用示例：**
    ```javascript
    const eventSource = new EventSource('/api/aiops');

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'plan') {
        console.log('诊断计划:', data.plan);
      } else if (data.type === 'step_complete') {
        console.log('步骤完成:', data.current_step);
      } else if (data.type === 'report') {
        console.log('最终报告:', data.report);
      } else if (data.type === 'complete') {
        console.log('诊断完成');
        eventSource.close();
      }
    };
    ```

    Args:
        request: AIOps 诊断请求

    Returns:
        SSE 事件流
    """
    session_id = request.session_id or "default"
    logger.info(f"[会话 {session_id}] 收到 AIOps 诊断请求（流式）")

    async def event_generator():
        try:
            async for event in aiops_service.diagnose(session_id=session_id):
                # 发送事件
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False)
                }

                # 如果是完成或错误事件，结束流
                if event.get("type") in ["complete", "error"]:
                    break

            logger.info(f"[会话 {session_id}] AIOps 诊断流式响应完成")

        except Exception as e:
            logger.error(f"[会话 {session_id}] AIOps 诊断流式响应异常: {e}", exc_info=True)
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "stage": "exception",
                    "message": f"诊断异常: {str(e)}"
                }, ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())


@router.get("/aiops/memory/cases")
async def list_aiops_memory_cases(
    limit: int = Query(default=20, ge=1, le=100, description="返回最近多少条诊断案例")
):
    """查询已经持久化的 AIOps 历史诊断案例。"""
    cases = aiops_memory_service.list_recent_cases(limit=limit)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": len(cases),
            "cases": cases,
        },
    }


@router.get("/aiops/memory/entities")
async def list_aiops_memory_entities(
    entity_type: str | None = Query(
        default=None,
        description="实体类型，可选值如 alert/service；不传则返回全部",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="返回最近多少条实体记忆"),
):
    """查询结构化实体记忆，例如告警名和服务名。"""
    entities = aiops_memory_service.list_entities(entity_type=entity_type, limit=limit)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": len(entities),
            "entities": entities,
        },
    }


@router.get("/aiops/memory/followups")
async def list_aiops_memory_followups(
    case_id: str | None = Query(default=None, description="按 case_id 过滤"),
    session_id: str | None = Query(default=None, description="按 session_id 过滤"),
    limit: int = Query(default=50, ge=1, le=200, description="返回最近多少条后续聊天记忆"),
):
    """查询 AI Ops 后续聊天沉淀出的关键记忆候选。"""
    followups = aiops_memory_service.list_followups(
        case_id=case_id,
        session_id=session_id,
        limit=limit,
    )
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": len(followups),
            "followups": followups,
        },
    }


@router.get("/aiops/memory/procedures")
async def list_aiops_memory_procedures(
    limit: int = Query(default=50, ge=1, le=200, description="返回最近多少条程序记忆")
):
    """查询从诊断报告和后续确认中沉淀出的程序记忆 SOP。"""
    procedures = aiops_memory_service.list_procedures(limit=limit)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": len(procedures),
            "procedures": procedures,
        },
    }
