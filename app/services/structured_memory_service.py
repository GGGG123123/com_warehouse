"""结构化记忆服务。

结构化记忆用于保存明确、稳定、可字段化的信息，例如用户偏好。
它不使用 embedding，而是通过 tenant_id / user_id / scope 精确隔离和查询。
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from app.services.memory_evaluator_service import memory_evaluator_service


DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "structured_memory.sqlite3"
DEFAULT_TENANT_ID = "local"
DEFAULT_USER_ID = "local_user"


@dataclass
class PreferenceCapture:
    """一次用户偏好捕获结果。"""

    preference_id: str
    tenant_id: str
    user_id: str
    scope: str
    session_id: str
    preference_key: str
    preference_value: str
    preference_type: str
    confidence: float
    source_text: str
    status: str


class StructuredMemoryService:
    """管理用户偏好等结构化记忆。"""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()
        logger.info(f"结构化记忆服务初始化完成: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """初始化用户偏好表。"""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    preference_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    session_id TEXT,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    preference_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_text TEXT NOT NULL,
                    source_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT,
                    expires_at TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(tenant_id, user_id, scope, preference_key)
                );

                CREATE INDEX IF NOT EXISTS idx_user_preferences_lookup
                    ON user_preferences(tenant_id, user_id, scope, status);
                CREATE INDEX IF NOT EXISTS idx_user_preferences_key
                    ON user_preferences(tenant_id, user_id, preference_key);
                CREATE INDEX IF NOT EXISTS idx_user_preferences_updated
                    ON user_preferences(updated_at);
                """
            )

    def build_user_memory_context(
        self,
        tenant_id: str | None,
        user_id: str | None,
        session_id: str | None,
        limit: int = 12,
    ) -> str:
        """读取当前用户相关偏好，并格式化为 system prompt 片段。"""
        memories = self.get_relevant_preferences(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            limit=limit,
        )
        if not memories:
            return ""

        lines = []
        for item in memories:
            lines.append(
                f"- {item['preference_key']}: {item['preference_value']} "
                f"(scope={item['scope']}, confidence={item['confidence']:.2f}, score={item['memory_score']:.2f})"
            )
        return "## 用户结构化记忆\n\n以下偏好仅适用于当前 tenant/user/scope，若用户本轮明确表达相反偏好，应以用户本轮指令为准：\n" + "\n".join(lines)

    def get_relevant_preferences(
        self,
        tenant_id: str | None,
        user_id: str | None,
        session_id: str | None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """按用户隔离读取偏好，并根据新鲜度、置信度、使用次数排序。"""
        tenant = normalize_tenant_id(tenant_id)
        user = normalize_user_id(user_id)
        safe_limit = max(1, min(limit, 50))
        now = utc_now()

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM user_preferences
                WHERE tenant_id = ?
                  AND status = 'active'
                  AND (
                    (scope = 'user' AND user_id = ?)
                    OR (scope = 'session' AND user_id = ? AND session_id = ?)
                    OR (scope = 'project' AND user_id = '*')
                  )
                  AND (expires_at IS NULL OR expires_at > ?)
                """,
                (tenant, user, user, session_id or "", now),
            ).fetchall()

        memories = [preference_row_to_dict(row) for row in rows]
        for item in memories:
            item["freshness_score"] = freshness_score(
                item.get("updated_at"),
                half_life_days=get_half_life_days(item.get("preference_type"), item.get("scope")),
            )
            item["memory_score"] = memory_score(item)

        memories.sort(key=lambda item: item["memory_score"], reverse=True)
        selected = memories[:safe_limit]
        self.mark_preferences_used([item["preference_id"] for item in selected])
        return selected

    def capture_user_preferences(
        self,
        tenant_id: str | None,
        user_id: str | None,
        session_id: str,
        user_message: str,
    ) -> list[PreferenceCapture]:
        """从用户消息中抽取稳定偏好，写入结构化记忆。"""
        tenant = normalize_tenant_id(tenant_id)
        user = normalize_user_id(user_id)
        candidates = extract_preference_candidates_with_model(user_message)
        captures: list[PreferenceCapture] = []

        for candidate in candidates:
            capture = self.upsert_preference(
                tenant_id=tenant,
                user_id=user,
                session_id=session_id,
                source_text=user_message,
                **candidate,
            )
            if capture:
                captures.append(capture)

        return captures

    def upsert_preference(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str,
        preference_key: str,
        preference_value: str,
        preference_type: str,
        confidence: float,
        scope: str = "user",
        source_text: str = "",
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PreferenceCapture | None:
        """新增或更新一条偏好。"""
        if not preference_key or not preference_value:
            return None

        now = utc_now()
        preference_id = f"pref-{uuid.uuid4().hex[:12]}"
        safe_scope = scope if scope in {"user", "session", "project"} else "user"
        db_user_id = "*" if safe_scope == "project" else user_id
        db_session_id = session_id if safe_scope == "session" else None

        with self._connection() as conn:
            existing = conn.execute(
                """
                SELECT preference_id, source_count, confidence
                FROM user_preferences
                WHERE tenant_id = ? AND user_id = ? AND scope = ? AND preference_key = ?
                """,
                (tenant_id, db_user_id, safe_scope, preference_key),
            ).fetchone()

            if existing:
                preference_id = str(existing["preference_id"])
                source_count = int(existing["source_count"]) + 1
                merged_confidence = max(float(existing["confidence"]), confidence)
                conn.execute(
                    """
                    UPDATE user_preferences
                    SET preference_value = ?,
                        preference_type = ?,
                        confidence = ?,
                        source_text = ?,
                        source_count = ?,
                        updated_at = ?,
                        expires_at = ?,
                        status = 'active',
                        metadata_json = ?
                    WHERE preference_id = ?
                    """,
                    (
                        preference_value,
                        preference_type,
                        merged_confidence,
                        source_text,
                        source_count,
                        now,
                        expires_at,
                        json_dumps(metadata or {}),
                        preference_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_preferences (
                        preference_id, tenant_id, user_id, scope, session_id,
                        preference_key, preference_value, preference_type,
                        confidence, source_text, source_count, created_at,
                        updated_at, last_used_at, expires_at, status, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL, ?, 'active', ?)
                    """,
                    (
                        preference_id,
                        tenant_id,
                        db_user_id,
                        safe_scope,
                        db_session_id,
                        preference_key,
                        preference_value,
                        preference_type,
                        confidence,
                        source_text,
                        now,
                        now,
                        expires_at,
                        json_dumps(metadata or {}),
                    ),
                )

        capture = PreferenceCapture(
            preference_id=preference_id,
            tenant_id=tenant_id,
            user_id=db_user_id,
            scope=safe_scope,
            session_id=session_id,
            preference_key=preference_key,
            preference_value=preference_value,
            preference_type=preference_type,
            confidence=confidence,
            source_text=source_text,
            status="active",
        )
        logger.info(
            "结构化记忆已写入: tenant={}, user={}, scope={}, key={}, value={}",
            tenant_id,
            db_user_id,
            safe_scope,
            preference_key,
            preference_value,
        )
        return capture

    def mark_preferences_used(self, preference_ids: list[str]) -> None:
        """更新偏好的最近使用时间。"""
        if not preference_ids:
            return
        now = utc_now()
        placeholders = ",".join("?" for _ in preference_ids)
        with self._connection() as conn:
            conn.execute(
                f"UPDATE user_preferences SET last_used_at = ? WHERE preference_id IN ({placeholders})",
                (now, *preference_ids),
            )

    def list_preferences(
        self,
        tenant_id: str | None = None,
        user_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询结构化偏好记忆。"""
        safe_limit = max(1, min(limit, 200))
        where = ["status = 'active'"]
        params: list[Any] = []
        if tenant_id:
            where.append("tenant_id = ?")
            params.append(normalize_tenant_id(tenant_id))
        if user_id:
            where.append("(user_id = ? OR user_id = '*')")
            params.append(normalize_user_id(user_id))
        if scope:
            where.append("scope = ?")
            params.append(scope)

        where_sql = " AND ".join(where)
        with self._connection() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM user_preferences
                WHERE {where_sql}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*params, safe_limit),
            ).fetchall()
        return [preference_row_to_dict(row) for row in rows]


def extract_preference_candidates_with_model(text: str) -> list[dict[str, Any]]:
    """优先使用记忆评估模型抽取用户偏好，失败时用规则兜底。"""
    try:
        candidates = memory_evaluator_service.extract_user_preferences(text)
        if candidates is not None:
            return candidates
    except Exception as exc:
        logger.warning(f"记忆评估模型抽取用户偏好失败，使用规则兜底: {exc}")

    return extract_preference_candidates_by_rules(text)


def extract_preference_candidates_by_rules(text: str) -> list[dict[str, Any]]:
    """规则兜底：从用户输入里提取稳定偏好。"""
    normalized = normalize_whitespace(text)
    if not normalized:
        return []

    durable = contains_any(
        normalized,
        ("以后", "以后都", "以后不要", "默认", "总是", "每次", "我喜欢", "我希望", "偏好", "记住", "不要再", "不用", "别用"),
    )
    session_only = contains_any(normalized, ("这次", "本次", "当前这个问题", "这个会话"))
    scope = "session" if session_only and not durable else "user"
    candidates: list[dict[str, Any]] = []

    def add(key: str, value: str, ptype: str, confidence: float = 0.86, force: bool = False) -> None:
        if force or durable or session_only:
            candidates.append(
                {
                    "preference_key": key,
                    "preference_value": value,
                    "preference_type": ptype,
                    "confidence": confidence,
                    "scope": scope,
                }
            )

    if contains_any(normalized, ("中文", "用中文", "中文回答")):
        add("response_language", "中文", "style", 0.92, force=durable)
    if contains_any(normalized, ("英文", "英语", "用英文")):
        add("response_language", "英文", "style", 0.88)

    if contains_any(normalized, ("详细解释", "讲详细", "说详细", "一步一步", "详细讲", "详细说明")):
        add("detail_level", "详细、分步骤解释", "style", 0.9)
    if contains_any(normalized, ("简洁", "简单说", "短一点", "别太长", "少说")):
        add("detail_level", "简洁回答", "style", 0.84)

    if contains_any(normalized, ("代码", "注释")) and contains_any(normalized, ("详细注释", "每一个代码", "注释详细", "写注释")):
        add("code_comment_style", "代码需要清晰且较详细的中文注释", "coding", 0.9, force=durable)

    if contains_any(normalized.lower(), ("mem0", "mem zero")) and contains_any(normalized, ("不用", "暂时不用", "不要用", "别用")):
        add("memory_provider", "暂时不用 Mem0，优先使用本地 SQLite + Milvus 方案", "tool_policy", 0.94, force=True)

    if contains_any(normalized.lower(), ("milvus", "muvils")):
        add("vector_database", "Milvus", "project", 0.82, force=durable)
    if contains_any(normalized, ("Prometheus", "prometheus")):
        add("monitoring_stack", "Prometheus", "project", 0.82, force=durable)
    if contains_any(normalized, ("CLS", "cls")):
        add("log_stack", "CLS / 本地日志查询", "project", 0.82, force=durable)
    if contains_any(normalized, ("AIOps", "aiops", "运维", "OnCall", "oncall")):
        add("domain_focus", "AIOps / OnCall 运维场景", "project", 0.82, force=durable)

    # 去重：同一条消息里同 key 只保留最后一次。
    by_key: dict[str, dict[str, Any]] = {}
    for item in candidates:
        by_key[item["preference_key"]] = item
    return list(by_key.values())


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def freshness_score(updated_at: str | None, half_life_days: float) -> float:
    """按半衰期计算新鲜度。"""
    if not updated_at:
        return 0.5
    try:
        dt = datetime.fromisoformat(updated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.5
    age_days = max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 86400)
    return math.exp(-age_days / max(half_life_days, 1.0))


def get_half_life_days(preference_type: str | None, scope: str | None) -> float:
    """不同结构化记忆使用不同半衰期。"""
    if scope == "session":
        return 7.0
    mapping = {
        "style": 180.0,
        "coding": 180.0,
        "tool_policy": 180.0,
        "project": 90.0,
        "domain": 365.0,
    }
    return mapping.get(preference_type or "", 120.0)


def memory_score(item: dict[str, Any]) -> float:
    confidence = float(item.get("confidence") or 0.0)
    freshness = float(item.get("freshness_score") or 0.0)
    source_count = int(item.get("source_count") or 1)
    usage_boost = 1.0 + min(math.log1p(source_count) * 0.06, 0.24)
    return confidence * freshness * usage_boost


def normalize_tenant_id(value: str | None) -> str:
    return normalize_identifier(value, DEFAULT_TENANT_ID)


def normalize_user_id(value: str | None) -> str:
    return normalize_identifier(value, DEFAULT_USER_ID)


def normalize_identifier(value: str | None, fallback: str) -> str:
    if not value or not str(value).strip():
        return fallback
    text = str(value).strip()
    return re.sub(r"[^A-Za-z0-9_.@-]", "_", text)[:80] or fallback


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return default


def preference_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["metadata"] = json_loads(data.pop("metadata_json", "{}"), {})
    return data


structured_memory_service = StructuredMemoryService()
