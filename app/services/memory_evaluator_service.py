"""基于独立小模型的长期记忆评估服务。

这个服务专门做三件事：
1. 判断 AIOps 后续聊天是否值得进入长期记忆；
2. 为完整 AIOps 诊断报告生成摘要和可复用 SOP；
3. 从用户消息中抽取结构化偏好记忆。

它和主聊天模型分开，默认使用 MEMORY_EVALUATOR_MODEL。
如果模型调用失败，调用方可以选择使用原来的保守兜底逻辑，避免记忆系统影响主流程。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory


FOLLOWUP_MEMORY_KINDS = {
    "resolution_confirmed",
    "action_taken",
    "root_cause_confirmed",
    "procedure_update",
    "user_observation",
    "none",
}

PREFERENCE_SCOPES = {"user", "session", "project"}
PREFERENCE_TYPES = {"style", "coding", "tool_policy", "project", "domain", "other"}


@dataclass
class MemoryEvaluation:
    """模型对一段聊天内容的长期记忆价值判断。"""

    should_store: bool
    memory_kind: str
    importance: float
    relevance: float
    novelty: float
    stability: float
    actionability: float
    final_score: float
    summary: str
    reason: str
    evaluator_model: str


class MemoryEvaluatorService:
    """调用独立模型，完成记忆判断和摘要。"""

    def __init__(self) -> None:
        self.enabled = bool(config.memory_evaluator_enabled)
        self.model_name = config.memory_evaluator_model
        self.store_threshold = float(config.memory_evaluator_store_threshold)
        self._models: dict[str, Any] = {}
        self._disabled_models: set[str] = set()
        self.last_model_name = self.model_name
        logger.info(
            "记忆评估模型服务初始化: enabled={}, model={}, threshold={}",
            self.enabled,
            self.model_name,
            self.store_threshold,
        )

    def _candidate_model_names(self) -> list[str]:
        """返回 evaluator 模型候选链。

        优先使用专用 evaluator 模型；如果账户额度或权限不可用，
        再退到当前 RAG 模型，保证仍然是模型判断，而不是直接规则判断。
        """
        names = [self.model_name]
        if config.rag_model and config.rag_model not in names:
            names.append(config.rag_model)
        enabled_names = [name for name in names if name not in self._disabled_models]
        return enabled_names or names

    def _get_model(self, model_name: str):
        """懒加载 evaluator 模型，避免服务启动时就额外创建连接。"""
        if model_name not in self._models:
            self._models[model_name] = llm_factory.create_chat_model(
                model=model_name,
                temperature=0.0,
                streaming=False,
            )
        return self._models[model_name]

    def evaluate_followup_memory(
        self,
        user_message: str,
        assistant_answer: str | None = None,
        case_context: dict[str, Any] | None = None,
        recent_followups: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """判断 AIOps 后续聊天是否值得进入长期记忆。"""
        if not self.enabled or not user_message.strip():
            return None

        prompt = {
            "user_message": user_message,
            "assistant_answer": assistant_answer or "",
            "case_context": compact_case_context(case_context or {}),
            "recent_stored_followups": [
                {
                    "memory_kind": item.get("memory_kind"),
                    "summary": item.get("summary"),
                    "content": truncate_text(str(item.get("content") or ""), 300),
                }
                for item in (recent_followups or [])[:8]
            ],
            "scoring_policy": {
                "importance": "这条信息是否关键，例如根因、实际动作、恢复结论、流程修正。",
                "relevance": "是否和当前 AIOps/OnCall 故障处理直接相关。",
                "novelty": "是否相对已有 followup 是新增事实，而不是重复解释。",
                "stability": "是否像稳定事实或确认结论，而不是临时猜测。",
                "actionability": "是否能指导未来相似故障处理。",
            },
        }

        system = (
            "你是 AIOps 长期记忆评估器。你只判断内容是否值得存入长期记忆，"
            "不要回答用户问题。请严格输出 JSON，不要输出 Markdown。\n\n"
            "只有这些内容值得存：根因确认、实际处理动作、恢复验证、流程修正、关键现场观察。"
            "普通追问、解释请求、寒暄、重复内容、临时猜测不要存。\n\n"
            "JSON 字段必须包含："
            "should_store, memory_kind, importance, relevance, novelty, stability, "
            "actionability, summary, reason。\n"
            "memory_kind 只能是 resolution_confirmed/action_taken/root_cause_confirmed/"
            "procedure_update/user_observation/none。"
            "所有分数是 0 到 1 的小数。summary 用中文，80 字以内。"
        )
        raw = self._invoke_json(system, json.dumps(prompt, ensure_ascii=False))
        if not isinstance(raw, dict):
            return None

        memory_kind = str(raw.get("memory_kind") or "none").strip()
        if memory_kind not in FOLLOWUP_MEMORY_KINDS:
            memory_kind = "none"

        evaluation = MemoryEvaluation(
            should_store=bool(raw.get("should_store")),
            memory_kind=memory_kind,
            importance=clamp_score(raw.get("importance")),
            relevance=clamp_score(raw.get("relevance")),
            novelty=clamp_score(raw.get("novelty")),
            stability=clamp_score(raw.get("stability")),
            actionability=clamp_score(raw.get("actionability")),
            final_score=0.0,
            summary=truncate_text(str(raw.get("summary") or ""), 280),
            reason=truncate_text(str(raw.get("reason") or ""), 280),
            evaluator_model=self.last_model_name,
        )
        evaluation.final_score = compute_memory_score(evaluation)

        if not evaluation.should_store or evaluation.memory_kind == "none":
            evaluation.final_score = min(evaluation.final_score, 0.49)

        return evaluation.__dict__

    def summarize_diagnosis_report(
        self,
        report: str,
        alert_names: list[str],
        services: list[str],
    ) -> str | None:
        """用 evaluator 模型压缩完整 AIOps 诊断报告。"""
        if not self.enabled or not report.strip():
            return None

        payload = {
            "alert_names": alert_names[:8],
            "services": services[:8],
            "report": truncate_text(report, 5200),
        }
        system = (
            "你是 AIOps 诊断报告摘要器。请只输出 JSON，不要输出 Markdown。"
            "把报告压缩成可放入长期记忆的中文摘要，保留：故障对象、关键证据、根因判断、"
            "处理动作、恢复验证、后续风险。不要编造报告中没有的事实。"
            "JSON 字段：summary。summary 控制在 600 字以内。"
        )
        raw = self._invoke_json(system, json.dumps(payload, ensure_ascii=False))
        if not isinstance(raw, dict):
            return None
        summary = str(raw.get("summary") or "").strip()
        return truncate_text(summary, 1200) if summary else None

    def extract_procedure_memory(
        self,
        report: str,
        alert_names: list[str],
        services: list[str],
        case_id: str,
    ) -> str | None:
        """从完整诊断报告中抽取可复用 SOP。"""
        if not self.enabled or not report.strip():
            return None

        payload = {
            "case_id": case_id,
            "alert_names": alert_names[:8],
            "services": services[:8],
            "report": truncate_text(report, 6000),
        }
        system = (
            "你是 AIOps 程序记忆抽取器。请只输出 JSON，不要输出 Markdown。"
            "从一次诊断报告中抽取可复用 SOP，而不是复述具体历史数值。"
            "必须去具体化：历史时间、一次性的数值、临时日志片段只能作为参考，不要当作下次事实。"
            "JSON 字段：procedure_text。procedure_text 使用 Markdown，包含："
            "# AIOps 可复用处理流程、适用场景、处理步骤、恢复验证、注意事项。"
            "如果报告没有可复用流程，procedure_text 返回空字符串。"
        )
        raw = self._invoke_json(system, json.dumps(payload, ensure_ascii=False))
        if not isinstance(raw, dict):
            return None
        procedure_text = str(raw.get("procedure_text") or "").strip()
        return truncate_text(procedure_text, 2600) if procedure_text else None

    def extract_user_preferences(self, user_message: str) -> list[dict[str, Any]] | None:
        """用 evaluator 模型抽取用户结构化偏好。"""
        if not self.enabled or not user_message.strip():
            return None

        system = (
            "你是用户结构化记忆抽取器。请只输出 JSON，不要输出 Markdown。"
            "只抽取用户明确表达的稳定偏好或本会话偏好，不要从普通问题中臆测偏好。"
            "可以抽取回答语言、详细程度、代码注释风格、工具/模型选择、项目技术栈、领域偏好。"
            "如果用户只是询问知识、讨论方案、表达临时事实，则返回空列表。\n\n"
            "JSON 字段：preferences。preferences 是数组，每项包含："
            "preference_key, preference_value, preference_type, confidence, scope, reason。"
            "scope 只能是 user/session/project。"
            "preference_type 只能是 style/coding/tool_policy/project/domain/other。"
            "confidence 是 0 到 1。preference_key 使用英文 snake_case。"
            "preference_value 用中文自然语言表达，例如“中文”“详细、分步骤解释”。"
        )
        raw = self._invoke_json(system, json.dumps({"user_message": user_message}, ensure_ascii=False))
        if not isinstance(raw, dict):
            return None

        preferences = raw.get("preferences")
        if not isinstance(preferences, list):
            return []

        cleaned: list[dict[str, Any]] = []
        for item in preferences[:8]:
            if not isinstance(item, dict):
                continue
            key = normalize_preference_key(str(item.get("preference_key") or ""))
            value = normalize_preference_value(
                key,
                str(item.get("preference_value") or "").strip(),
            )
            if not key or not value:
                continue

            preference_type = str(item.get("preference_type") or "other").strip()
            if preference_type not in PREFERENCE_TYPES:
                preference_type = "other"

            scope = str(item.get("scope") or "user").strip()
            if scope not in PREFERENCE_SCOPES:
                scope = "user"

            cleaned.append(
                {
                    "preference_key": key,
                    "preference_value": value,
                    "preference_type": preference_type,
                    "confidence": clamp_score(item.get("confidence"), default=0.75),
                    "scope": scope,
                    "metadata": {
                        "reason": truncate_text(str(item.get("reason") or ""), 240),
                        "evaluator_model": self.last_model_name,
                    },
                }
            )

        return dedupe_preferences(cleaned)

    def _invoke_json(self, system: str, user: str) -> Any:
        """调用模型并解析 JSON。"""
        last_error: Exception | None = None

        for model_name in self._candidate_model_names():
            try:
                model = self._get_model(model_name)
                response = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
                content = str(getattr(response, "content", response) or "").strip()
                json_text = extract_json_text(content)
                parsed = json.loads(json_text)
                self.last_model_name = model_name
                return parsed
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.warning(
                    "记忆评估模型返回非 JSON，model={}, error={}",
                    model_name,
                    exc,
                )
            except Exception as exc:
                last_error = exc
                self._disabled_models.add(model_name)
                logger.warning("记忆评估模型调用失败，model={}, error={}", model_name, exc)

        if last_error:
            raise last_error
        return None


def compact_case_context(case: dict[str, Any]) -> dict[str, Any]:
    """压缩 case 上下文，减少 evaluator token 消耗。"""
    if not case:
        return {}
    return {
        "case_id": case.get("case_id"),
        "title": case.get("title"),
        "summary": truncate_text(str(case.get("summary") or ""), 600),
        "alert_names": case.get("alert_names") or [],
        "services": case.get("services") or [],
        "status": case.get("status"),
    }


def compute_memory_score(evaluation: MemoryEvaluation) -> float:
    """综合重要性、相关性、新颖性、稳定性和可操作性。"""
    score = (
        evaluation.importance * 0.30
        + evaluation.relevance * 0.25
        + evaluation.novelty * 0.20
        + evaluation.stability * 0.15
        + evaluation.actionability * 0.10
    )
    return round(clamp_score(score), 4)


def clamp_score(value: Any, default: float = 0.0) -> float:
    """把模型输出的分数规整到 0-1。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def extract_json_text(content: str) -> str:
    """从模型输出中剥离代码块并取出 JSON。"""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    first_candidates = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not first_candidates:
        return text
    start = min(first_candidates)
    end = max(text.rfind("}"), text.rfind("]"))
    if end > start:
        return text[start : end + 1]
    return text[start:]


def normalize_preference_key(value: str) -> str:
    """规范化 preference_key。"""
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80]


def normalize_preference_value(key: str, value: str) -> str:
    """把模型输出的常见英文短值规整成更适合中文 prompt 的偏好值。"""
    normalized = value.strip()
    lowered = normalized.lower()

    mappings = {
        "response_language": {
            "chinese": "中文",
            "zh": "中文",
            "zh-cn": "中文",
            "mandarin": "中文",
            "english": "英文",
            "en": "英文",
        },
        "detail_level": {
            "detailed": "详细、分步骤解释",
            "detail": "详细、分步骤解释",
            "concise": "简洁回答",
            "short": "简洁回答",
            "brief": "简洁回答",
        },
        "code_comment_style": {
            "detailed": "代码需要清晰且较详细的中文注释",
            "detail": "代码需要清晰且较详细的中文注释",
            "verbose": "代码需要清晰且较详细的中文注释",
        },
    }

    if key in mappings and lowered in mappings[key]:
        return mappings[key][lowered]

    return truncate_text(normalized, 300)


def dedupe_preferences(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同一条消息里同 key 只保留最后一次。"""
    by_key: dict[str, dict[str, Any]] = {}
    for item in items:
        by_key[item["preference_key"]] = item
    return list(by_key.values())


def truncate_text(text: str, max_chars: int) -> str:
    """限制文本长度，避免记忆评估请求过大。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


memory_evaluator_service = MemoryEvaluatorService()
