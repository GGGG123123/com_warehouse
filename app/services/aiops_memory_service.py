"""AIOps 长期记忆服务。

这个服务不使用 Mem0，而是把记忆分成两类存储：
1. SQLite：保存可追溯的结构化诊断案例和实体信息。
2. Milvus：保存历史故障摘要，供后续 AIOps 语义召回。
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from loguru import logger

from app.core.milvus_client import milvus_manager
from app.config import config
from app.services.memory_evaluator_service import memory_evaluator_service


DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "aiops_memory.sqlite3"
MILVUS_MEMORY_SOURCE_PREFIX = "aiops_memory://diagnosis_case/"
MILVUS_PROCEDURE_SOURCE_PREFIX = "aiops_memory://procedure/"
MILVUS_FOLLOWUP_SOURCE_PREFIX = "aiops_memory://followup/"
MAX_REPORT_SNIPPET_CHARS = 4200
MAX_SUMMARY_CHARS = 1200
MAX_PROCEDURE_CHARS = 2600
IMPORTANT_FOLLOWUP_THRESHOLD = 0.65
_vector_embedding_service: Any | None = None
_vector_store_manager: Any | None = None


@dataclass
class DiagnosisCase:
    """一次 AIOps 诊断沉淀下来的长期记忆。"""

    case_id: str
    session_id: str
    created_at: str
    title: str
    summary: str
    report: str
    alert_names: list[str]
    services: list[str]
    severity: str
    status: str
    milvus_source: str
    memory_status: str = "active"
    duplicate_of: str | None = None
    seen_count: int = 1
    updated_at: str = ""


@dataclass
class ProcedureMemory:
    """从一次诊断中沉淀出来的可复用处理流程。"""

    procedure_id: str
    source_case_id: str
    session_id: str
    created_at: str
    title: str
    procedure_text: str
    alert_names: list[str]
    services: list[str]
    status: str
    milvus_source: str
    duplicate_of: str | None = None
    seen_count: int = 1
    updated_at: str = ""


@dataclass
class FollowupCapture:
    """AI Ops 后续聊天中的关键记忆候选。"""

    followup_id: str
    case_id: str
    session_id: str
    created_at: str
    role: str
    content: str
    memory_kind: str
    importance: float
    status: str
    summary: str
    duplicate_of: str | None = None
    seen_count: int = 1
    updated_at: str = ""
    evaluator_model: str = ""
    reason: str = ""


class AIOpsMemoryService:
    """AIOps 记忆管理。

    设计原则：
    - 实时指标和原始日志不直接写入长期记忆，避免过期数据污染召回。
    - 只有诊断完成后的报告、根因、建议和告警摘要进入长期记忆。
    - 结构化字段放 SQLite，语义检索摘要放 Milvus。
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()
        logger.info(f"AIOps 长期记忆服务初始化完成: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        """创建 SQLite 连接。每次操作单独连接，避免跨线程复用连接。"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        """自动提交并关闭 SQLite 连接。"""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """初始化长期记忆表。"""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS aiops_diagnosis_cases (
                    case_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    report TEXT NOT NULL,
                    alert_names_json TEXT NOT NULL,
                    services_json TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    memory_status TEXT NOT NULL DEFAULT 'active',
                    duplicate_of TEXT,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    milvus_source TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_aiops_cases_created_at
                    ON aiops_diagnosis_cases(created_at);
                CREATE INDEX IF NOT EXISTS idx_aiops_cases_session_id
                    ON aiops_diagnosis_cases(session_id);
                CREATE INDEX IF NOT EXISTS idx_aiops_cases_status
                    ON aiops_diagnosis_cases(status);

                CREATE TABLE IF NOT EXISTS aiops_entities (
                    entity_type TEXT NOT NULL,
                    entity_name TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    latest_case_id TEXT,
                    PRIMARY KEY (entity_type, entity_name)
                );

                CREATE INDEX IF NOT EXISTS idx_aiops_entities_type
                    ON aiops_entities(entity_type);

                CREATE TABLE IF NOT EXISTS aiops_active_cases (
                    session_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_aiops_active_cases_case_id
                    ON aiops_active_cases(case_id);

                CREATE TABLE IF NOT EXISTS aiops_case_followups (
                    followup_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    memory_kind TEXT NOT NULL,
                    importance REAL NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    evaluator_model TEXT NOT NULL DEFAULT '',
                    duplicate_of TEXT,
                    seen_count INTEGER NOT NULL DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_aiops_followups_case_id
                    ON aiops_case_followups(case_id);
                CREATE INDEX IF NOT EXISTS idx_aiops_followups_session_id
                    ON aiops_case_followups(session_id);
                CREATE INDEX IF NOT EXISTS idx_aiops_followups_status
                    ON aiops_case_followups(status);

                CREATE TABLE IF NOT EXISTS aiops_procedure_memories (
                    procedure_id TEXT PRIMARY KEY,
                    source_case_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    title TEXT NOT NULL,
                    procedure_text TEXT NOT NULL,
                    alert_names_json TEXT NOT NULL,
                    services_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duplicate_of TEXT,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    milvus_source TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_aiops_procedures_case_id
                    ON aiops_procedure_memories(source_case_id);
                CREATE INDEX IF NOT EXISTS idx_aiops_procedures_created_at
                    ON aiops_procedure_memories(created_at);
                """
            )
            self._migrate_db(conn)

    def _migrate_db(self, conn: sqlite3.Connection) -> None:
        """为旧 SQLite 数据库补齐去重、合并和状态管理字段。"""
        self._ensure_column(conn, "aiops_diagnosis_cases", "updated_at", "TEXT")
        self._ensure_column(conn, "aiops_diagnosis_cases", "memory_status", "TEXT NOT NULL DEFAULT 'active'")
        self._ensure_column(conn, "aiops_diagnosis_cases", "duplicate_of", "TEXT")
        self._ensure_column(conn, "aiops_diagnosis_cases", "seen_count", "INTEGER NOT NULL DEFAULT 1")

        self._ensure_column(conn, "aiops_case_followups", "updated_at", "TEXT")
        self._ensure_column(conn, "aiops_case_followups", "reason", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "aiops_case_followups", "evaluator_model", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "aiops_case_followups", "duplicate_of", "TEXT")
        self._ensure_column(conn, "aiops_case_followups", "seen_count", "INTEGER NOT NULL DEFAULT 1")

        self._ensure_column(conn, "aiops_procedure_memories", "updated_at", "TEXT")
        self._ensure_column(conn, "aiops_procedure_memories", "duplicate_of", "TEXT")
        self._ensure_column(conn, "aiops_procedure_memories", "seen_count", "INTEGER NOT NULL DEFAULT 1")

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_aiops_cases_memory_status
                ON aiops_diagnosis_cases(memory_status);
            CREATE INDEX IF NOT EXISTS idx_aiops_cases_duplicate_of
                ON aiops_diagnosis_cases(duplicate_of);
            CREATE INDEX IF NOT EXISTS idx_aiops_followups_duplicate_of
                ON aiops_case_followups(duplicate_of);
            CREATE INDEX IF NOT EXISTS idx_aiops_procedures_duplicate_of
                ON aiops_procedure_memories(duplicate_of);
            """
        )

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        """如果旧表缺少字段，则用 ALTER TABLE 补上。"""
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        columns = {str(row["name"]) for row in rows}
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

    def build_task_with_memory(
        self, task_text: str
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """
        为 AI Ops 任务拼接记忆上下文。

        Returns:
            tuple: (带记忆上下文的任务文本, 当前告警快照, 历史案例, 程序记忆)
        """
        alerts = self.fetch_current_alerts()
        alert_context = self.format_alerts_for_prompt(alerts)

        memory_query = "\n".join(part for part in [task_text, alert_context] if part.strip())
        historical_cases = self.search_similar_cases(memory_query, top_k=3)
        procedures = self.search_similar_procedures(memory_query, top_k=3)
        history_context = self.format_cases_for_prompt(historical_cases)
        procedure_context = self.format_procedures_for_prompt(procedures)

        context_blocks = []
        if alert_context:
            context_blocks.append(
                "## 当前 Prometheus 告警快照\n"
                "以下内容只用于规划初始方向，执行过程中仍需通过工具查询最新指标和日志：\n\n"
                f"{alert_context}"
            )
        if history_context:
            context_blocks.append(
                "## 历史故障记忆\n"
                "以下是从长期记忆中召回的相似历史案例，可作为排查参考，但不能替代实时证据：\n\n"
                f"{history_context}"
            )
        if procedure_context:
            context_blocks.append(
                "## 程序记忆 / 可复用 SOP\n"
                "以下是从历史处理过程中沉淀出来的通用处理流程，可作为执行计划参考：\n\n"
                f"{procedure_context}"
            )

        if not context_blocks:
            return task_text, alerts, historical_cases, procedures

        task_with_memory = f"{task_text}\n\n---\n\n## AIOps 记忆上下文\n\n" + "\n\n".join(context_blocks)
        return task_with_memory, alerts, historical_cases, procedures

    def fetch_current_alerts(self) -> list[dict[str, Any]]:
        """读取 Prometheus 当前告警，用于构造历史记忆检索词和最终案例元数据。"""
        from app.tools.query_metrics_alerts import query_prometheus_alerts_api, _simplify_alerts

        result, err = query_prometheus_alerts_api()
        if err:
            logger.warning(f"读取 Prometheus 告警失败，跳过告警快照: {err}")
            return []
        if result.get("status") != "success":
            logger.warning(f"Prometheus 告警接口返回非成功状态: {result}")
            return []

        alerts, _ = _simplify_alerts(result)
        return alerts

    def save_diagnosis_report(
        self,
        session_id: str,
        report: str,
        alerts: list[dict[str, Any]] | None = None,
    ) -> DiagnosisCase | None:
        """保存 AI Ops 最终诊断报告，并写入 Milvus 历史故障摘要。"""
        if not report or not report.strip():
            logger.warning("AI Ops 报告为空，跳过长期记忆保存")
            return None

        created_at = utc_now()
        case_id = f"aiops-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        current_alerts = alerts if alerts is not None else self.fetch_current_alerts()
        alert_names = extract_alert_names(current_alerts, report)
        services = extract_services(current_alerts, report)
        severity = pick_highest_severity(current_alerts)
        status = infer_case_status(current_alerts)
        title = build_case_title(report, alert_names)
        summary = summarize_report_with_model(report, alert_names, services)
        duplicate_case = self._find_duplicate_case(summary, alert_names, services)
        duplicate_of = str(duplicate_case["case_id"]) if duplicate_case else None
        memory_status = "duplicate" if duplicate_of else "active"
        milvus_source = f"{MILVUS_MEMORY_SOURCE_PREFIX}{case_id}"

        case = DiagnosisCase(
            case_id=case_id,
            session_id=session_id,
            created_at=created_at,
            updated_at=created_at,
            title=title,
            summary=summary,
            report=report,
            alert_names=alert_names,
            services=services,
            severity=severity,
            status=status,
            milvus_source=milvus_source,
            memory_status=memory_status,
            duplicate_of=duplicate_of,
        )

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO aiops_diagnosis_cases (
                    case_id, session_id, created_at, updated_at, title, summary, report,
                    alert_names_json, services_json, severity, status, milvus_source,
                    memory_status, duplicate_of, seen_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case.case_id,
                    case.session_id,
                    case.created_at,
                    case.updated_at,
                    case.title,
                    case.summary,
                    case.report,
                    json_dumps(case.alert_names),
                    json_dumps(case.services),
                    case.severity,
                    case.status,
                    case.milvus_source,
                    case.memory_status,
                    case.duplicate_of,
                    case.seen_count,
                ),
            )

        if duplicate_of:
            self._increment_case_seen_count(duplicate_of)
            logger.info(
                f"AI Ops 诊断报告已保存为重复情节记忆: {case.case_id}, canonical={duplicate_of}"
            )

        self._upsert_entities(case)
        if case.memory_status == "active":
            self._index_case_summary_to_milvus(case)
        else:
            logger.info(f"跳过重复情节记忆的 Milvus 索引: {case.case_id}")
        self._save_active_case(case.session_id, case.case_id, status="active")
        self._save_and_index_procedure_memory(case)
        logger.info(f"AI Ops 诊断报告已保存为长期记忆: {case.case_id}")
        return case

    def _save_active_case(self, session_id: str, case_id: str, status: str = "active") -> None:
        """记录某个聊天会话当前正在跟进的 AIOps case。"""
        now = utc_now()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO aiops_active_cases (
                    session_id, case_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    case_id = excluded.case_id,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (session_id, case_id, status, now, now),
            )

    def get_active_case_id(self, session_id: str) -> str | None:
        """获取当前 session 正在跟进的 AIOps case。"""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT case_id FROM aiops_active_cases
                WHERE session_id = ? AND status IN ('active', 'resolved')
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return str(row["case_id"])

    def _upsert_entities(self, case: DiagnosisCase) -> None:
        """把告警名、服务名保存为结构化实体记忆。"""
        now = utc_now()
        entities: list[tuple[str, str, dict[str, Any]]] = []

        for alert_name in case.alert_names:
            entities.append(
                (
                    "alert",
                    alert_name,
                    {
                        "latest_case_id": case.case_id,
                        "services": case.services,
                        "severity": case.severity,
                        "status": case.status,
                    },
                )
            )

        for service in case.services:
            entities.append(
                (
                    "service",
                    service,
                    {
                        "latest_case_id": case.case_id,
                        "alert_names": case.alert_names,
                        "severity": case.severity,
                        "status": case.status,
                    },
                )
            )

        if not entities:
            return

        with self._connection() as conn:
            for entity_type, entity_name, value in entities:
                conn.execute(
                    """
                    INSERT INTO aiops_entities (
                        entity_type, entity_name, value_json, first_seen_at,
                        last_seen_at, seen_count, latest_case_id
                    ) VALUES (?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(entity_type, entity_name) DO UPDATE SET
                        value_json = excluded.value_json,
                        last_seen_at = excluded.last_seen_at,
                        seen_count = aiops_entities.seen_count + 1,
                        latest_case_id = excluded.latest_case_id
                    """,
                    (
                        entity_type,
                        entity_name,
                        json_dumps(value),
                        now,
                        now,
                        case.case_id,
                    ),
                )

    def _find_duplicate_case(
        self,
        summary: str,
        alert_names: list[str],
        services: list[str],
    ) -> dict[str, Any] | None:
        """在 SQLite 中查找相似历史诊断，避免相似案例反复进入 Milvus。"""
        if not summary.strip():
            return None

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM aiops_diagnosis_cases
                WHERE memory_status = 'active'
                ORDER BY created_at DESC
                LIMIT 80
                """
            ).fetchall()

        best_case: dict[str, Any] | None = None
        best_score = 0.0
        for row in rows:
            item = case_row_to_dict(row)
            if not has_context_overlap(alert_names, item.get("alert_names", [])) and not has_context_overlap(services, item.get("services", [])):
                continue
            score = text_similarity(summary, str(item.get("summary") or ""))
            if score > best_score:
                best_score = score
                best_case = item

        if best_case and best_score >= config.memory_case_duplicate_similarity:
            best_case["duplicate_similarity"] = best_score
            return best_case
        return None

    def _increment_case_seen_count(self, case_id: str) -> None:
        """重复情节记忆命中时，只增加 canonical case 的出现次数。"""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE aiops_diagnosis_cases
                SET seen_count = COALESCE(seen_count, 1) + 1,
                    updated_at = ?
                WHERE case_id = ?
                """,
                (utc_now(), case_id),
            )

    def _index_case_summary_to_milvus(self, case: DiagnosisCase) -> None:
        """把历史故障摘要写入 Milvus，用于之后语义召回。"""
        if case.memory_status != "active":
            logger.info(f"跳过非 active 情节记忆索引: {case.case_id}, status={case.memory_status}")
            return

        try:
            content = build_milvus_memory_content(case)
            metadata = {
                "_source": case.milvus_source,
                "_file_name": f"{case.case_id}.md",
                "_extension": ".aiops-memory",
                "memory_type": "aiops_incident_case",
                "chunk_type": "incident_summary",
                "case_id": case.case_id,
                "session_id": case.session_id,
                "created_at": case.created_at,
                "alert_names": case.alert_names,
                "services": case.services,
                "severity": case.severity,
                "status": case.status,
                "memory_status": case.memory_status,
                "duplicate_of": case.duplicate_of,
                "seen_count": case.seen_count,
            }
            get_vector_store_manager().add_documents([Document(page_content=content, metadata=metadata)])
        except Exception as exc:
            # 结构化数据库已经保存成功，Milvus 失败不应影响用户拿到诊断报告。
            logger.error(f"AI Ops 历史故障摘要写入 Milvus 失败: {exc}")

    def _save_and_index_procedure_memory(self, case: DiagnosisCase) -> ProcedureMemory | None:
        """从完整诊断报告中提炼可复用处理流程，并写入 SQLite + Milvus。"""
        procedure_text = build_procedure_memory_content(case)
        if not procedure_text.strip():
            return None

        duplicate_procedure = self._find_duplicate_procedure(
            procedure_text=procedure_text,
            alert_names=case.alert_names,
            services=case.services,
        )
        if duplicate_procedure:
            self._merge_duplicate_procedure(
                procedure_id=str(duplicate_procedure["procedure_id"]),
                source_case_id=case.case_id,
            )
            logger.info(
                "AI Ops 程序记忆命中相似 SOP，不新增 Milvus 文档: source_case={}, canonical={}, similarity={}",
                case.case_id,
                duplicate_procedure["procedure_id"],
                duplicate_procedure.get("duplicate_similarity"),
            )
            return procedure_from_dict(duplicate_procedure)

        procedure = ProcedureMemory(
            procedure_id=f"proc-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            source_case_id=case.case_id,
            session_id=case.session_id,
            created_at=utc_now(),
            updated_at=utc_now(),
            title=build_procedure_title(case),
            procedure_text=procedure_text,
            alert_names=case.alert_names,
            services=case.services,
            status="candidate",
            milvus_source="",
        )
        procedure.milvus_source = f"{MILVUS_PROCEDURE_SOURCE_PREFIX}{procedure.procedure_id}"

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO aiops_procedure_memories (
                    procedure_id, source_case_id, session_id, created_at, updated_at, title,
                    procedure_text, alert_names_json, services_json, status,
                    duplicate_of, seen_count, milvus_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    procedure.procedure_id,
                    procedure.source_case_id,
                    procedure.session_id,
                    procedure.created_at,
                    procedure.updated_at,
                    procedure.title,
                    procedure.procedure_text,
                    json_dumps(procedure.alert_names),
                    json_dumps(procedure.services),
                    procedure.status,
                    procedure.duplicate_of,
                    procedure.seen_count,
                    procedure.milvus_source,
                ),
            )

        self._index_procedure_to_milvus(procedure, chunk_type="procedure_summary")
        logger.info(
            f"AI Ops 程序记忆摘要已保存: {procedure.procedure_id}, source_case={case.case_id}"
        )
        return procedure

    def _find_duplicate_procedure(
        self,
        procedure_text: str,
        alert_names: list[str],
        services: list[str],
    ) -> dict[str, Any] | None:
        """查找相似 SOP，避免程序记忆不断膨胀。"""
        if not procedure_text.strip():
            return None

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM aiops_procedure_memories
                WHERE duplicate_of IS NULL
                  AND status IN ('candidate', 'active')
                ORDER BY created_at DESC
                LIMIT 100
                """
            ).fetchall()

        best_procedure: dict[str, Any] | None = None
        best_score = 0.0
        for row in rows:
            item = procedure_row_to_dict(row)
            if not has_context_overlap(alert_names, item.get("alert_names", [])) and not has_context_overlap(services, item.get("services", [])):
                continue
            score = text_similarity(procedure_text, str(item.get("procedure_text") or ""))
            if score > best_score:
                best_score = score
                best_procedure = item

        if best_procedure and best_score >= config.memory_procedure_duplicate_similarity:
            best_procedure["duplicate_similarity"] = best_score
            return best_procedure
        return None

    def _merge_duplicate_procedure(self, procedure_id: str, source_case_id: str) -> None:
        """相似 SOP 命中时，不新增，只提升 canonical SOP 的出现次数。"""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE aiops_procedure_memories
                SET seen_count = COALESCE(seen_count, 1) + 1,
                    updated_at = ?,
                    source_case_id = CASE
                        WHEN instr(source_case_id, ?) > 0 THEN source_case_id
                        ELSE source_case_id || ',' || ?
                    END
                WHERE procedure_id = ?
                """,
                (utc_now(), source_case_id, source_case_id, procedure_id),
            )

    def _index_procedure_to_milvus(
        self, procedure: ProcedureMemory, chunk_type: str = "procedure_summary"
    ) -> None:
        """把程序记忆 SOP 写入 Milvus。"""
        try:
            metadata = {
                "_source": procedure.milvus_source,
                "_file_name": f"{procedure.procedure_id}.md",
                "_extension": ".aiops-procedure",
                "memory_type": "aiops_procedure",
                "chunk_type": chunk_type,
                "procedure_id": procedure.procedure_id,
                "source_case_id": procedure.source_case_id,
                "session_id": procedure.session_id,
                "created_at": procedure.created_at,
                "alert_names": procedure.alert_names,
                "services": procedure.services,
                "status": procedure.status,
                "duplicate_of": procedure.duplicate_of,
                "seen_count": procedure.seen_count,
            }
            get_vector_store_manager().add_documents(
                [Document(page_content=procedure.procedure_text, metadata=metadata)]
            )
        except Exception as exc:
            logger.error(f"AI Ops 程序记忆写入 Milvus 失败: {exc}")

    def capture_chat_followup(
        self,
        session_id: str,
        user_message: str,
        assistant_answer: str | None = None,
    ) -> FollowupCapture | None:
        """
        在 AI Ops 后续聊天中筛选重要信息，并追加到当前 active case。

        普通解释类追问只留在 checkpointer；根因确认、处理动作、恢复验证、流程修正
        才会进入长期记忆候选。
        """
        case_id = self.get_active_case_id(session_id)
        if not case_id:
            return None

        case = self.get_case(case_id) or {}
        recent_followups = self.list_followups(case_id=case_id, limit=8)
        classification = evaluate_followup_memory_with_model(
            user_message=user_message,
            assistant_answer=assistant_answer,
            case_context=case,
            recent_followups=recent_followups,
        )
        threshold = getattr(
            memory_evaluator_service,
            "store_threshold",
            IMPORTANT_FOLLOWUP_THRESHOLD,
        )
        if classification["final_score"] < threshold:
            return None

        duplicate_followup = self._find_duplicate_followup(
            case_id=case_id,
            memory_kind=classification["memory_kind"],
            summary=classification["summary"],
            content=user_message,
        )
        if duplicate_followup:
            merged = self._merge_duplicate_followup(
                duplicate_followup=duplicate_followup,
                classification=classification,
                content=user_message,
            )
            if merged.memory_kind in {"resolution_confirmed", "procedure_update"}:
                self.commit_case_followups(case_id)
            return merged

        followup = FollowupCapture(
            followup_id=f"follow-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            session_id=session_id,
            created_at=utc_now(),
            updated_at=utc_now(),
            role="user",
            content=user_message.strip(),
            memory_kind=classification["memory_kind"],
            importance=float(classification["final_score"]),
            status="candidate",
            summary=classification["summary"],
            evaluator_model=str(classification.get("evaluator_model") or ""),
            reason=str(classification.get("reason") or ""),
        )

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO aiops_case_followups (
                    followup_id, case_id, session_id, created_at, updated_at,
                    role, content, memory_kind, importance, status, summary,
                    reason, evaluator_model, duplicate_of, seen_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    followup.followup_id,
                    followup.case_id,
                    followup.session_id,
                    followup.created_at,
                    followup.updated_at,
                    followup.role,
                    followup.content,
                    followup.memory_kind,
                    followup.importance,
                    followup.status,
                    followup.summary,
                    followup.reason,
                    followup.evaluator_model,
                    followup.duplicate_of,
                    followup.seen_count,
                ),
            )

        logger.info(
            f"AI Ops 后续聊天已保存为长期记忆候选: {followup.followup_id}, "
            f"kind={followup.memory_kind}, case={case_id}"
        )

        if followup.memory_kind in {"resolution_confirmed", "procedure_update"}:
            self.commit_case_followups(case_id)

        return followup

    def _find_duplicate_followup(
        self,
        case_id: str,
        memory_kind: str,
        summary: str,
        content: str,
    ) -> dict[str, Any] | None:
        """同一个 case 内查找重复 followup，避免一句恢复结论重复保存多次。"""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM aiops_case_followups
                WHERE case_id = ?
                  AND duplicate_of IS NULL
                  AND memory_kind = ?
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (case_id, memory_kind),
            ).fetchall()

        best: dict[str, Any] | None = None
        best_score = 0.0
        candidate_text = "\n".join(part for part in [summary, content] if part)
        for row in rows:
            item = dict(row)
            existing_summary = str(item.get("summary") or "")
            existing_content = str(item.get("content") or "")
            existing_text = "\n".join(
                part for part in [existing_summary, existing_content] if part
            )
            score = max(
                text_similarity(summary, existing_summary),
                text_similarity(content, existing_content),
                text_similarity(candidate_text, existing_text),
            )
            if score > best_score:
                best_score = score
                best = item

        if best and best_score >= config.memory_followup_duplicate_similarity:
            best["duplicate_similarity"] = best_score
            return best
        return None

    def _merge_duplicate_followup(
        self,
        duplicate_followup: dict[str, Any],
        classification: dict[str, Any],
        content: str,
    ) -> FollowupCapture:
        """重复 followup 命中时只更新已有记录，不新增候选。"""
        now = utc_now()
        followup_id = str(duplicate_followup["followup_id"])
        new_importance = max(
            float(duplicate_followup.get("importance") or 0.0),
            float(classification.get("final_score") or 0.0),
        )
        new_summary = choose_better_summary(
            str(duplicate_followup.get("summary") or ""),
            str(classification.get("summary") or ""),
        )

        with self._connection() as conn:
            conn.execute(
                """
                UPDATE aiops_case_followups
                SET seen_count = COALESCE(seen_count, 1) + 1,
                    updated_at = ?,
                    importance = ?,
                    summary = ?,
                    reason = ?,
                    evaluator_model = ?,
                    status = CASE
                        WHEN status = 'committed' THEN status
                        ELSE 'merged_duplicate'
                    END
                WHERE followup_id = ?
                """,
                (
                    now,
                    new_importance,
                    new_summary,
                    str(classification.get("reason") or duplicate_followup.get("reason") or ""),
                    str(classification.get("evaluator_model") or duplicate_followup.get("evaluator_model") or ""),
                    followup_id,
                ),
            )

        logger.info(
            "AI Ops 后续聊天命中重复记忆，已合并: followup={}, similarity={}",
            followup_id,
            duplicate_followup.get("duplicate_similarity"),
        )

        return FollowupCapture(
            followup_id=followup_id,
            case_id=str(duplicate_followup["case_id"]),
            session_id=str(duplicate_followup["session_id"]),
            created_at=str(duplicate_followup["created_at"]),
            updated_at=now,
            role=str(duplicate_followup.get("role") or "user"),
            content=content.strip(),
            memory_kind=str(duplicate_followup["memory_kind"]),
            importance=new_importance,
            status="merged_duplicate",
            summary=new_summary,
            duplicate_of=followup_id,
            seen_count=int(duplicate_followup.get("seen_count") or 1) + 1,
            evaluator_model=str(classification.get("evaluator_model") or ""),
            reason=str(classification.get("reason") or ""),
        )

    def commit_case_followups(self, case_id: str) -> None:
        """当用户确认恢复或修正流程时，把候选 followup 汇总写入 Milvus。"""
        case = self.get_case(case_id)
        if not case:
            return
        followups = self.list_followups(case_id=case_id, limit=50)
        if not followups:
            return

        try:
            content = build_followup_memory_content(case, followups)
            source = f"{MILVUS_FOLLOWUP_SOURCE_PREFIX}{case_id}-{uuid.uuid4().hex[:8]}"
            metadata = {
                "_source": source,
                "_file_name": f"{case_id}-followup.md",
                "_extension": ".aiops-followup",
                "memory_type": "aiops_incident_case",
                "chunk_type": "incident_followup",
                "case_id": case_id,
                "session_id": case.get("session_id"),
                "created_at": utc_now(),
                "alert_names": case.get("alert_names", []),
                "services": case.get("services", []),
                "status": "followup_committed",
            }
            get_vector_store_manager().add_documents([Document(page_content=content, metadata=metadata)])
            self._save_followup_procedure_update(case, followups)
            with self._connection() as conn:
                conn.execute(
                    "UPDATE aiops_case_followups SET status = 'committed' WHERE case_id = ?",
                    (case_id,),
                )
                conn.execute(
                    """
                    UPDATE aiops_active_cases
                    SET status = 'resolved', updated_at = ?
                    WHERE case_id = ?
                    """,
                    (utc_now(), case_id),
                )
            logger.info(f"AI Ops 后续聊天已汇总提交到长期记忆: case={case_id}")
        except Exception as exc:
            logger.error(f"提交 AI Ops 后续聊天长期记忆失败: {exc}")

    def _save_followup_procedure_update(
        self, case: dict[str, Any], followups: list[dict[str, Any]]
    ) -> None:
        """从后续聊天中提炼新的程序记忆更新。"""
        procedure_text = build_followup_procedure_content(case, followups)
        if not procedure_text.strip():
            return

        alert_names = list(case.get("alert_names") or [])
        services = list(case.get("services") or [])
        duplicate_procedure = self._find_duplicate_procedure(
            procedure_text=procedure_text,
            alert_names=alert_names,
            services=services,
        )
        if duplicate_procedure:
            self._merge_duplicate_procedure(
                procedure_id=str(duplicate_procedure["procedure_id"]),
                source_case_id=str(case["case_id"]),
            )
            logger.info(
                "后续聊天 SOP 命中相似程序记忆，不新增: case={}, canonical={}, similarity={}",
                case["case_id"],
                duplicate_procedure["procedure_id"],
                duplicate_procedure.get("duplicate_similarity"),
            )
            return

        procedure = ProcedureMemory(
            procedure_id=f"proc-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            source_case_id=str(case["case_id"]),
            session_id=str(case["session_id"]),
            created_at=utc_now(),
            updated_at=utc_now(),
            title=f"后续确认流程: {case.get('title') or case['case_id']}",
            procedure_text=procedure_text,
            alert_names=alert_names,
            services=services,
            status="candidate",
            milvus_source="",
        )
        procedure.milvus_source = f"{MILVUS_PROCEDURE_SOURCE_PREFIX}{procedure.procedure_id}"

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO aiops_procedure_memories (
                    procedure_id, source_case_id, session_id, created_at, updated_at, title,
                    procedure_text, alert_names_json, services_json, status,
                    duplicate_of, seen_count, milvus_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    procedure.procedure_id,
                    procedure.source_case_id,
                    procedure.session_id,
                    procedure.created_at,
                    procedure.updated_at,
                    procedure.title,
                    procedure.procedure_text,
                    json_dumps(procedure.alert_names),
                    json_dumps(procedure.services),
                    procedure.status,
                    procedure.duplicate_of,
                    procedure.seen_count,
                    procedure.milvus_source,
                ),
            )
        self._index_procedure_to_milvus(procedure, chunk_type="procedure_followup_update")

    def search_similar_cases(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """从 Milvus 中召回相似历史故障案例。"""
        if not query or not query.strip():
            return []

        try:
            collection = get_milvus_collection()
            query_vector = get_vector_embedding_service().embed_query(query)
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            expr = 'metadata["memory_type"] == "aiops_incident_case"'

            try:
                results = collection.search(
                    data=[query_vector],
                    anns_field="vector",
                    param=search_params,
                    limit=top_k,
                    expr=expr,
                    output_fields=["id", "content", "metadata"],
                )
            except Exception as expr_exc:
                logger.warning(f"按 memory_type 过滤历史案例失败，降级为搜索后过滤: {expr_exc}")
                results = collection.search(
                    data=[query_vector],
                    anns_field="vector",
                    param=search_params,
                    limit=max(top_k * 5, top_k),
                    output_fields=["id", "content", "metadata"],
                )

            cases: list[dict[str, Any]] = []
            for hits in results:
                for hit in hits:
                    metadata = hit.entity.get("metadata") or {}
                    if metadata.get("memory_type") != "aiops_incident_case":
                        continue
                    if metadata.get("memory_status") in {"duplicate", "outdated", "deleted"}:
                        continue
                    cases.append(
                        {
                            "id": hit.entity.get("id"),
                            "content": hit.entity.get("content") or "",
                            "score": hit.distance,
                            "metadata": metadata,
                        }
                    )
                    if len(cases) >= top_k:
                        return cases
            return cases
        except Exception as exc:
            logger.warning(f"历史故障记忆检索失败，跳过召回: {exc}")
            return []

    def search_similar_procedures(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """从 Milvus 中召回可复用程序记忆 SOP。"""
        if not query or not query.strip():
            return []

        try:
            collection = get_milvus_collection()
            query_vector = get_vector_embedding_service().embed_query(query)
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            expr = 'metadata["memory_type"] == "aiops_procedure"'

            try:
                results = collection.search(
                    data=[query_vector],
                    anns_field="vector",
                    param=search_params,
                    limit=top_k,
                    expr=expr,
                    output_fields=["id", "content", "metadata"],
                )
            except Exception as expr_exc:
                logger.warning(f"按 memory_type 过滤程序记忆失败，降级为搜索后过滤: {expr_exc}")
                results = collection.search(
                    data=[query_vector],
                    anns_field="vector",
                    param=search_params,
                    limit=max(top_k * 5, top_k),
                    output_fields=["id", "content", "metadata"],
                )

            procedures: list[dict[str, Any]] = []
            for hits in results:
                for hit in hits:
                    metadata = hit.entity.get("metadata") or {}
                    if metadata.get("memory_type") != "aiops_procedure":
                        continue
                    if metadata.get("duplicate_of"):
                        continue
                    procedures.append(
                        {
                            "id": hit.entity.get("id"),
                            "content": hit.entity.get("content") or "",
                            "score": hit.distance,
                            "metadata": metadata,
                        }
                    )
                    if len(procedures) >= top_k:
                        return procedures
            return procedures
        except Exception as exc:
            logger.warning(f"程序记忆检索失败，跳过召回: {exc}")
            return []

    def format_alerts_for_prompt(self, alerts: list[dict[str, Any]]) -> str:
        """把当前告警快照压缩成适合放进 prompt 的文本。"""
        if not alerts:
            return ""

        lines = []
        for alert in alerts[:8]:
            labels = alert.get("labels") or {}
            alert_name = alert.get("alert_name") or labels.get("alertname") or "unknown"
            service = labels.get("service") or labels.get("job") or "unknown"
            severity = labels.get("severity") or "unknown"
            state = alert.get("state") or "unknown"
            duration = alert.get("duration") or "unknown"
            summary = alert.get("summary") or alert.get("description") or ""
            lines.append(
                f"- 告警: {alert_name}; 服务: {service}; 级别: {severity}; "
                f"状态: {state}; 持续: {duration}; 摘要: {summary}"
            )
        return "\n".join(lines)

    def format_cases_for_prompt(self, cases: list[dict[str, Any]]) -> str:
        """把历史案例召回结果压缩成 prompt 上下文。"""
        if not cases:
            return ""

        parts = []
        for index, case in enumerate(cases, 1):
            metadata = case.get("metadata") or {}
            content = normalize_whitespace(case.get("content") or "")
            snippet = truncate_text(content, 900)
            parts.append(
                f"【历史案例 {index}】\n"
                f"案例ID: {metadata.get('case_id', 'unknown')}\n"
                f"时间: {metadata.get('created_at', 'unknown')}\n"
                f"告警: {', '.join(metadata.get('alert_names') or []) or 'unknown'}\n"
                f"服务: {', '.join(metadata.get('services') or []) or 'unknown'}\n"
                f"内容摘要: {snippet}"
            )
        return "\n\n".join(parts)

    def format_procedures_for_prompt(self, procedures: list[dict[str, Any]]) -> str:
        """把程序记忆召回结果压缩成 prompt 上下文。"""
        if not procedures:
            return ""

        parts = []
        for index, procedure in enumerate(procedures, 1):
            metadata = procedure.get("metadata") or {}
            content = normalize_whitespace(procedure.get("content") or "")
            snippet = truncate_text(content, 900)
            parts.append(
                f"【程序记忆 {index}】\n"
                f"流程ID: {metadata.get('procedure_id', 'unknown')}\n"
                f"来源案例: {metadata.get('source_case_id', 'unknown')}\n"
                f"告警: {', '.join(metadata.get('alert_names') or []) or 'unknown'}\n"
                f"服务: {', '.join(metadata.get('services') or []) or 'unknown'}\n"
                f"SOP 摘要: {snippet}"
            )
        return "\n\n".join(parts)

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        """按 case_id 查询完整情节记忆。"""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM aiops_diagnosis_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        if not row:
            return None
        return case_row_to_dict(row)

    def list_recent_cases(self, limit: int = 20) -> list[dict[str, Any]]:
        """查询最近的 AI Ops 诊断案例。"""
        safe_limit = max(1, min(limit, 100))
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM aiops_diagnosis_cases
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [case_row_to_dict(row) for row in rows]

    def list_entities(self, entity_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """查询结构化实体记忆。"""
        safe_limit = max(1, min(limit, 200))
        with self._connection() as conn:
            if entity_type:
                rows = conn.execute(
                    """
                    SELECT * FROM aiops_entities
                    WHERE entity_type = ?
                    ORDER BY last_seen_at DESC
                    LIMIT ?
                    """,
                    (entity_type, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM aiops_entities
                    ORDER BY last_seen_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
        return [entity_row_to_dict(row) for row in rows]

    def list_followups(
        self,
        case_id: str | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询 AI Ops 后续聊天沉淀的关键记忆候选。"""
        safe_limit = max(1, min(limit, 200))
        where = []
        params: list[Any] = []
        if case_id:
            where.append("case_id = ?")
            params.append(case_id)
        if session_id:
            where.append("session_id = ?")
            params.append(session_id)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        with self._connection() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM aiops_case_followups
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_procedures(self, limit: int = 50) -> list[dict[str, Any]]:
        """查询从历史处理流程中沉淀出的程序记忆。"""
        safe_limit = max(1, min(limit, 200))
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM aiops_procedure_memories
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [procedure_row_to_dict(row) for row in rows]


def get_milvus_collection():
    """获取已连接的 Milvus collection。"""
    try:
        return milvus_manager.get_collection()
    except Exception:
        milvus_manager.connect()
        return milvus_manager.get_collection()


def get_vector_embedding_service() -> Any:
    """懒加载 embedding 服务，避免导入记忆模块时强制连接 Milvus。"""
    global _vector_embedding_service
    if _vector_embedding_service is None:
        from app.services.vector_embedding_service import vector_embedding_service

        _vector_embedding_service = vector_embedding_service
    return _vector_embedding_service


def get_vector_store_manager() -> Any:
    """懒加载向量库管理器，避免 Milvus 不可用时影响 SQLite 记忆。"""
    global _vector_store_manager
    if _vector_store_manager is None:
        from app.services.vector_store_manager import vector_store_manager

        _vector_store_manager = vector_store_manager
    return _vector_store_manager


def utc_now() -> str:
    """当前 UTC 时间 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    """统一 JSON 序列化。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: str, default: Any) -> Any:
    """安全 JSON 反序列化。"""
    try:
        return json.loads(value)
    except Exception:
        return default


def has_context_overlap(left: list[str], right: list[str]) -> bool:
    """判断两条记忆的告警或服务上下文是否有交集。

    如果某一侧没有结构化字段，不强行阻断比较，避免旧数据无法参与去重。
    """
    if not left or not right:
        return True
    left_set = {normalize_key(item) for item in left if item}
    right_set = {normalize_key(item) for item in right if item}
    return bool(left_set & right_set)


def text_similarity(left: str, right: str) -> float:
    """计算两段中文/英文文本的相似度，用于存储前去重。

    这里不用模型二次判断，避免每次写库多一次模型费用。
    相似度取 SequenceMatcher 和字符 bigram Jaccard 的较大值。
    """
    left_norm = normalize_for_similarity(left)
    right_norm = normalize_for_similarity(right)
    if not left_norm or not right_norm:
        return 0.0

    shorter, longer = sorted((left_norm, right_norm), key=len)
    if len(shorter) >= 16 and shorter in longer:
        return 1.0

    sequence_score = SequenceMatcher(None, left_norm, right_norm).ratio()
    jaccard_score = jaccard_similarity(char_ngrams(left_norm), char_ngrams(right_norm))
    return max(sequence_score, jaccard_score)


def normalize_for_similarity(text: str) -> str:
    """压缩文本，去掉多数标点，让中文短句更容易比较。"""
    text = normalize_whitespace(text).lower()
    return re.sub(r"[\s,，.。;；:：!！?？`'\"“”‘’()\[\]{}<>《》|/\\\-_*#]+", "", text)


def char_ngrams(text: str, n: int = 2) -> set[str]:
    """生成字符 ngram 集合。"""
    if len(text) <= n:
        return {text}
    return {text[index : index + n] for index in range(0, len(text) - n + 1)}


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    """集合 Jaccard 相似度。"""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def normalize_key(value: str) -> str:
    """规范化告警名/服务名，便于上下文交集判断。"""
    return re.sub(r"[^a-z0-9_-]+", "", str(value).lower())


def choose_better_summary(old_summary: str, new_summary: str) -> str:
    """重复 followup 合并时选择信息量更高的摘要。"""
    old = old_summary.strip()
    new = new_summary.strip()
    if not old:
        return new
    if not new:
        return old
    if len(new) > len(old) and text_similarity(old, new) < 0.98:
        return truncate_text(new, 280)
    return old


def extract_alert_names(alerts: list[dict[str, Any]], report: str) -> list[str]:
    """从当前告警和报告文本中提取告警名称。"""
    names: list[str] = []
    for alert in alerts:
        labels = alert.get("labels") or {}
        name = str(alert.get("alert_name") or labels.get("alertname") or "").strip()
        if name and name not in names:
            names.append(name)

    for name in re.findall(r"\b[A-Z][A-Za-z0-9_]*(?:High|Down|Error|Warning|Critical)[A-Za-z0-9_]*\b", report):
        if name not in names:
            names.append(name)

    return names[:12]


def extract_services(alerts: list[dict[str, Any]], report: str) -> list[str]:
    """从告警 labels 和报告文本中提取服务名。"""
    services: list[str] = []
    for alert in alerts:
        labels = alert.get("labels") or {}
        service = str(labels.get("service") or labels.get("job") or "").strip()
        if service and service not in services:
            services.append(service)

    for service in re.findall(r"\b[a-z][a-z0-9_-]{2,}(?:-service|-agent|-gateway)?\b", report):
        if service in {"warning", "critical", "pending", "firing", "unknown"}:
            continue
        if service not in services:
            services.append(service)

    return services[:12]


def pick_highest_severity(alerts: list[dict[str, Any]]) -> str:
    """选出最高告警级别。"""
    order = {"critical": 3, "warning": 2, "info": 1}
    highest = "unknown"
    highest_score = 0
    for alert in alerts:
        labels = alert.get("labels") or {}
        severity = str(labels.get("severity") or "").lower()
        score = order.get(severity, 0)
        if score > highest_score:
            highest = severity
            highest_score = score
    return highest


def infer_case_status(alerts: list[dict[str, Any]]) -> str:
    """根据 Prometheus 告警状态推断案例状态。"""
    states = {str(alert.get("state") or "").lower() for alert in alerts}
    if "firing" in states:
        return "firing"
    if "pending" in states:
        return "pending"
    if alerts:
        return "active"
    return "completed"


def build_case_title(report: str, alert_names: list[str]) -> str:
    """构造历史案例标题。"""
    if alert_names:
        return f"AI Ops 诊断: {', '.join(alert_names[:3])}"

    for line in report.splitlines():
        stripped = line.strip(" #")
        if stripped and len(stripped) <= 80:
            return stripped
    return "AI Ops 诊断报告"


def summarize_report_with_model(report: str, alert_names: list[str], services: list[str]) -> str:
    """优先使用记忆评估模型生成诊断摘要，失败时用规则兜底。"""
    try:
        summary = memory_evaluator_service.summarize_diagnosis_report(
            report=report,
            alert_names=alert_names,
            services=services,
        )
        if summary:
            return summary
    except Exception as exc:
        logger.warning(f"记忆评估模型生成诊断摘要失败，使用规则兜底: {exc}")

    return summarize_report_by_rules(report, alert_names, services)


def summarize_report_by_rules(report: str, alert_names: list[str], services: list[str]) -> str:
    """规则兜底摘要。"""
    normalized = normalize_whitespace(report)
    prefix_parts = []
    if alert_names:
        prefix_parts.append(f"告警: {', '.join(alert_names[:6])}")
    if services:
        prefix_parts.append(f"服务: {', '.join(services[:6])}")

    prefix = "；".join(prefix_parts)
    body = truncate_text(normalized, MAX_SUMMARY_CHARS)
    if prefix:
        return f"{prefix}。{body}"
    return body


def build_milvus_memory_content(case: DiagnosisCase) -> str:
    """构造写入 Milvus 的历史故障摘要文档。"""
    report_snippet = truncate_text(case.report, MAX_REPORT_SNIPPET_CHARS)
    return (
        "# AIOps 历史故障案例\n\n"
        f"案例ID: {case.case_id}\n"
        f"时间: {case.created_at}\n"
        f"会话: {case.session_id}\n"
        f"标题: {case.title}\n"
        f"告警: {', '.join(case.alert_names) or '无'}\n"
        f"服务: {', '.join(case.services) or '未知'}\n"
        f"级别: {case.severity}\n"
        f"状态: {case.status}\n\n"
        "## 摘要\n\n"
        f"{case.summary}\n\n"
        "## 原始报告节选\n\n"
        f"{report_snippet}"
    )


def build_procedure_title(case: DiagnosisCase) -> str:
    """构造程序记忆标题。"""
    if case.alert_names:
        return f"{', '.join(case.alert_names[:3])} 处理 SOP"
    if case.services:
        return f"{', '.join(case.services[:3])} 运维处理 SOP"
    return "AIOps 可复用处理流程"


def build_procedure_memory_content(case: DiagnosisCase) -> str:
    """优先使用记忆评估模型抽取程序记忆，失败时用规则兜底。"""
    try:
        procedure_text = memory_evaluator_service.extract_procedure_memory(
            report=case.report,
            alert_names=case.alert_names,
            services=case.services,
            case_id=case.case_id,
        )
        if procedure_text:
            return procedure_text
    except Exception as exc:
        logger.warning(f"记忆评估模型抽取程序记忆失败，使用规则兜底: {exc}")

    return build_procedure_memory_content_by_rules(case)


def build_procedure_memory_content_by_rules(case: DiagnosisCase) -> str:
    """规则兜底：从单次诊断报告中提炼去具体化的程序记忆。"""
    steps = extract_action_steps(case.report)
    verification_steps = extract_verification_steps(case.report)

    if not steps:
        steps = build_default_steps(case)
    if not verification_steps:
        verification_steps = [
            "再次查询 Prometheus 告警状态，确认 pending/firing 告警是否恢复。",
            "复查相关指标趋势，确认 CPU、内存、磁盘或业务指标回到合理范围。",
            "查询最近一段时间日志，确认 error、exception、timeout 等异常没有继续增长。",
        ]

    step_text = "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps[:10], 1))
    verification_text = "\n".join(
        f"{idx}. {step}" for idx, step in enumerate(verification_steps[:6], 1)
    )

    content = (
        "# AIOps 可复用处理流程\n\n"
        f"来源案例: {case.case_id}\n"
        f"适用告警: {', '.join(case.alert_names) or '通用告警'}\n"
        f"适用服务: {', '.join(case.services) or '通用服务'}\n"
        f"流程状态: candidate\n\n"
        "## 适用场景\n\n"
        "当出现相同或相似告警、指标异常、日志异常时，可参考此流程。执行时必须重新查询实时 Prometheus 指标和 CLS/本地日志，不要直接复用历史数值。\n\n"
        "## 处理步骤\n\n"
        f"{step_text}\n\n"
        "## 恢复验证\n\n"
        f"{verification_text}\n\n"
        "## 注意事项\n\n"
        "- 这是从一次诊断报告中提炼出的候选 SOP，遇到新故障时需要结合实时证据确认。\n"
        "- 不要把历史案例中的具体时间、百分比、日志片段当成本次事实。\n"
    )
    return truncate_text(content, MAX_PROCEDURE_CHARS)


def extract_action_steps(report: str) -> list[str]:
    """从报告中抽取可复用的处理/排查步骤。"""
    keywords = (
        "查询", "检查", "确认", "查看", "分析", "清理", "删除", "扩容", "回滚",
        "重启", "调整", "配置", "释放", "定位", "排查", "验证", "监控", "日志",
        "Prometheus", "CLS", "告警", "指标", "磁盘", "内存", "CPU",
    )
    steps: list[str] = []
    for line in report.splitlines():
        text = clean_step_line(line)
        if not text:
            continue
        if not any(keyword in text for keyword in keywords):
            continue
        if len(text) < 8 or len(text) > 180:
            continue
        add_unique(steps, text)
        if len(steps) >= 10:
            break
    return steps


def extract_verification_steps(report: str) -> list[str]:
    """从报告中抽取恢复验证步骤。"""
    keywords = ("验证", "恢复", "确认", "告警", "指标", "日志", "正常", "下降", "解除")
    steps: list[str] = []
    for line in report.splitlines():
        text = clean_step_line(line)
        if not text:
            continue
        if any(keyword in text for keyword in keywords):
            if 8 <= len(text) <= 180:
                add_unique(steps, text)
        if len(steps) >= 6:
            break
    return steps


def build_default_steps(case: DiagnosisCase) -> list[str]:
    """当报告里没有清晰步骤时，生成保守的通用处理步骤。"""
    alert_text = "、".join(case.alert_names) if case.alert_names else "当前告警"
    service_text = "、".join(case.services) if case.services else "目标服务"
    return [
        f"查询 Prometheus 当前告警，确认 {alert_text} 的状态、持续时间和影响对象。",
        f"查询 {service_text} 相关 CPU、内存、磁盘或业务指标，判断异常趋势和峰值。",
        f"查询 {service_text} 最近 15 分钟日志，重点关注 error、exception、timeout 等关键词。",
        "从知识库召回对应 runbook/SOP，确认该类告警的标准排查顺序。",
        "结合实时指标、日志证据和历史案例判断根因，避免只凭历史记忆下结论。",
        "执行最小影响的处理动作，并记录实际操作和观察结果。",
    ]


def clean_step_line(line: str) -> str:
    """清理报告中的列表/Markdown 前缀。"""
    text = line.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^\|", "", text).strip()
    text = re.sub(r"^\s*(?:[-*+]\s+|\d+[\.、)]\s*)", "", text)
    text = text.strip(" |-")
    if not text or set(text) <= {"-", "|", " "}:
        return ""
    return text


def add_unique(items: list[str], value: str) -> None:
    """按标准化文本去重追加。"""
    normalized = normalize_whitespace(value)
    if not normalized:
        return
    existing = {normalize_whitespace(item) for item in items}
    if normalized not in existing:
        items.append(normalized)


def classify_followup_memory(
    user_message: str,
    assistant_answer: str | None = None,
) -> dict[str, Any]:
    """规则兜底：判断后续聊天是否值得进入长期记忆候选。"""
    text = normalize_whitespace(user_message)
    if len(text) < 6:
        return {"memory_kind": "none", "importance": 0.0, "final_score": 0.0, "summary": ""}

    checks: list[tuple[str, float, tuple[str, ...]]] = [
        (
            "resolution_confirmed",
            0.95,
            ("恢复了", "解决了", "好了", "正常了", "告警消失", "告警恢复", "不报警", "验证通过"),
        ),
        (
            "action_taken",
            0.88,
            ("我清理", "我删除", "我扩容", "我回滚", "我重启", "我调整", "我修复", "我执行", "已经清理", "已经删除", "已经回滚", "已经重启"),
        ),
        (
            "root_cause_confirmed",
            0.86,
            ("根因", "原因是", "确认是", "确实是", "是因为", "导致", "问题在", "发现是"),
        ),
        (
            "procedure_update",
            0.82,
            ("下次", "以后", "流程", "步骤", "SOP", "runbook", "不对", "应该先", "优先", "改成"),
        ),
        (
            "user_observation",
            0.72,
            ("我发现", "我看到", "日志", "指标", "磁盘", "内存", "CPU", "timeout", "error", "exception", "超过", "降到", "下降到"),
        ),
    ]

    lowered = text.lower()
    for memory_kind, importance, keywords in checks:
        if any(keyword.lower() in lowered for keyword in keywords):
            return {
                "memory_kind": memory_kind,
                "importance": importance,
                "final_score": importance,
                "summary": build_followup_summary(memory_kind, text),
            }

    return {"memory_kind": "none", "importance": 0.0, "final_score": 0.0, "summary": ""}


def evaluate_followup_memory_with_model(
    user_message: str,
    assistant_answer: str | None = None,
    case_context: dict[str, Any] | None = None,
    recent_followups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """优先用记忆评估模型判断是否存储，失败时使用规则兜底。"""
    try:
        evaluation = memory_evaluator_service.evaluate_followup_memory(
            user_message=user_message,
            assistant_answer=assistant_answer,
            case_context=case_context,
            recent_followups=recent_followups,
        )
        if evaluation:
            return {
                "memory_kind": evaluation.get("memory_kind") or "none",
                "importance": float(evaluation.get("importance") or 0.0),
                "final_score": float(evaluation.get("final_score") or 0.0),
                "summary": evaluation.get("summary") or "",
                "reason": evaluation.get("reason") or "",
                "evaluator_model": evaluation.get("evaluator_model") or "",
            }
    except Exception as exc:
        logger.warning(f"记忆评估模型判断 followup 失败，使用规则兜底: {exc}")

    fallback = classify_followup_memory(user_message, assistant_answer)
    fallback["evaluator_model"] = "rule_fallback"
    return fallback


def build_followup_summary(memory_kind: str, text: str) -> str:
    """生成后续聊天记忆候选摘要。"""
    labels = {
        "resolution_confirmed": "恢复验证",
        "action_taken": "实际处理动作",
        "root_cause_confirmed": "根因确认",
        "procedure_update": "流程修正",
        "user_observation": "现场补充",
    }
    label = labels.get(memory_kind, "后续补充")
    return f"{label}: {truncate_text(text, 280)}"


def build_followup_memory_content(case: dict[str, Any], followups: list[dict[str, Any]]) -> str:
    """把后续关键聊天汇总成情节记忆补充。"""
    lines = []
    for item in reversed(followups):
        lines.append(
            f"- [{item.get('memory_kind')}] {item.get('summary') or item.get('content')}"
        )
    return (
        "# AIOps 后续处理复盘\n\n"
        f"关联案例: {case.get('case_id')}\n"
        f"标题: {case.get('title')}\n"
        f"告警: {', '.join(case.get('alert_names') or []) or '无'}\n"
        f"服务: {', '.join(case.get('services') or []) or '未知'}\n\n"
        "## 后续关键事实\n\n"
        + "\n".join(lines)
    )


def build_followup_procedure_content(case: dict[str, Any], followups: list[dict[str, Any]]) -> str:
    """从后续聊天沉淀程序记忆更新。"""
    useful = [
        item for item in followups
        if item.get("memory_kind") in {"action_taken", "resolution_confirmed", "procedure_update"}
    ]
    if not useful:
        return ""

    steps = []
    for item in reversed(useful):
        add_unique(steps, item.get("summary") or item.get("content") or "")

    step_text = "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps[:8], 1))
    return (
        "# AIOps 后续确认的可复用处理流程\n\n"
        f"来源案例: {case.get('case_id')}\n"
        f"适用告警: {', '.join(case.get('alert_names') or []) or '通用告警'}\n"
        f"适用服务: {', '.join(case.get('services') or []) or '通用服务'}\n\n"
        "## 从后续聊天确认的流程要点\n\n"
        f"{step_text}\n\n"
        "## 使用方式\n\n"
        "下次遇到相似告警时，可把这些要点作为候选 SOP 参考，但仍需重新查询实时指标和日志验证。"
    )


def normalize_whitespace(text: str) -> str:
    """压缩空白，保留基本可读性。"""
    return re.sub(r"\s+", " ", text).strip()


def truncate_text(text: str, max_chars: int) -> str:
    """截断文本，避免超过 Milvus content 字段长度。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def case_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """SQLite 诊断案例行转字典。"""
    data = dict(row)
    data["alert_names"] = json_loads(data.pop("alert_names_json", "[]"), [])
    data["services"] = json_loads(data.pop("services_json", "[]"), [])
    return data


def entity_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """SQLite 实体行转字典。"""
    data = dict(row)
    data["value"] = json_loads(data.pop("value_json", "{}"), {})
    return data


def procedure_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """SQLite 程序记忆行转字典。"""
    data = dict(row)
    data["alert_names"] = json_loads(data.pop("alert_names_json", "[]"), [])
    data["services"] = json_loads(data.pop("services_json", "[]"), [])
    return data


def procedure_from_dict(data: dict[str, Any]) -> ProcedureMemory:
    """把已有程序记忆行转换为 ProcedureMemory 对象。"""
    return ProcedureMemory(
        procedure_id=str(data.get("procedure_id") or ""),
        source_case_id=str(data.get("source_case_id") or ""),
        session_id=str(data.get("session_id") or ""),
        created_at=str(data.get("created_at") or utc_now()),
        updated_at=str(data.get("updated_at") or data.get("created_at") or utc_now()),
        title=str(data.get("title") or ""),
        procedure_text=str(data.get("procedure_text") or ""),
        alert_names=list(data.get("alert_names") or []),
        services=list(data.get("services") or []),
        status=str(data.get("status") or "candidate"),
        milvus_source=str(data.get("milvus_source") or ""),
        duplicate_of=data.get("duplicate_of"),
        seen_count=int(data.get("seen_count") or 1),
    )


# 全局单例
aiops_memory_service = AIOpsMemoryService()
