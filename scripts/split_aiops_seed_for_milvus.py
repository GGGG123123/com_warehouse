"""把 AIOps 结构化 JSONL 切成适合 Milvus 入库的 chunk。

这个脚本只负责“切分和预览”，不会连接 Milvus，也不会调用 embedding。
你可以先检查输出的 JSONL，确认每个 chunk 的 content 和 metadata 是否合理，
再决定是否执行真正的向量入库脚本。

运行:
    python scripts/split_aiops_seed_for_milvus.py

输入:
    data/aiops_seed/aiops_seed_records.jsonl

输出:
    data/aiops_seed/aiops_seed_milvus_chunks.jsonl
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


# 原始结构化数据。每一行是一条完整的 runbook、故障案例或告警规则。
INPUT_JSONL_PATH = Path("data/aiops_seed/aiops_seed_records.jsonl")

# 切分后的 Milvus 预入库数据。每一行对应一个向量库 chunk。
OUTPUT_CHUNKS_PATH = Path("data/aiops_seed/aiops_seed_milvus_chunks.jsonl")

# 单个 chunk 的推荐长度。这个项目当前 config.chunk_max_size=800，
# DocumentSplitterService 二次切分实际使用 1600。这里取 1400，给上下文前缀留一点余量。
MAX_CHARS = 1400

# 当某个语义块仍然过长时，按段落兜底切分，并保留少量重叠，避免上下文断裂。
OVERLAP_CHARS = 100


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 文件，每一行解析成一个 dict。"""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL 第 {line_no} 行解析失败: {exc}") from exc
    return records


def split_markdown_sections(content: str) -> tuple[str, dict[str, str]]:
    """把 Markdown 拆成标题和二级标题 section。

    返回:
        title: 文档一级标题，例如 "# api-gateway - HighCPUUsage 运维处置知识"
        sections: key 是二级标题文本，value 是包含标题和正文的完整 section
    """
    lines = content.splitlines()
    title = ""
    sections: dict[str, list[str]] = {}
    current_heading = ""

    for line in lines:
        if line.startswith("# ") and not title:
            title = line.strip()
            continue

        if line.startswith("## "):
            current_heading = line.removeprefix("## ").strip()
            sections[current_heading] = [line]
            continue

        if current_heading:
            sections[current_heading].append(line)

    return title, {heading: "\n".join(part).strip() for heading, part in sections.items()}


def build_context_prefix(record: dict[str, Any]) -> str:
    """生成每个 chunk 都携带的上下文前缀。

    向量检索时，用户的问题通常会带着服务名、告警名、级别、故障现象。
    如果 chunk 被切开后丢掉这些字段，召回质量会明显下降，所以每个 chunk 都补上。
    """
    metadata = record.get("metadata", {})
    lines = [
        f"文档ID: {record.get('id', '')}",
        f"数据类型: {record.get('doc_type') or metadata.get('doc_type', '')}",
        f"告警名称: {record.get('alert_name') or metadata.get('alert_name', '')}",
        f"告警分类: {record.get('category') or metadata.get('category', '')}",
        f"告警级别: {record.get('severity') or metadata.get('severity', '')}",
    ]

    service_name = record.get("service_name") or metadata.get("service_name")
    if service_name:
        lines.extend(
            [
                f"服务名称: {service_name}",
                f"服务角色: {record.get('service_role') or metadata.get('service_role', '')}",
                f"命名空间: {record.get('namespace') or metadata.get('namespace', '')}",
                f"责任团队: {record.get('owner') or metadata.get('owner', '')}",
            ]
        )

    trigger = record.get("trigger")
    if trigger:
        lines.append(f"触发条件: {trigger}")

    return "\n".join(line for line in lines if not line.endswith(": "))


def group_sections(doc_type: str, sections: dict[str, str]) -> list[tuple[str, list[str]]]:
    """按照业务语义决定每类文档如何切分。

    这里不是机械按字符切，而是把用户最可能一起问到的内容放在同一个 chunk。
    """
    if doc_type == "aiops_runbook":
        return [
            ("overview", ["元数据", "触发条件", "症状描述", "推荐 PromQL", "推荐日志查询"]),
            ("diagnosis", ["常见根因", "立即处置", "诊断步骤"]),
            ("verification", ["验证标准", "预防措施", "Agent 使用提示"]),
        ]

    if doc_type == "aiops_incident_case":
        return [
            ("incident_evidence", ["元数据", "事件摘要", "关键证据", "根因判断"]),
            ("incident_resolution", ["处置过程", "恢复验证", "复盘关注点"]),
        ]

    if doc_type == "aiops_alert_rule":
        return [
            (
                "alert_rule",
                [
                    "元数据",
                    "触发条件",
                    "PromQL",
                    "推荐 PromQL",
                    "推荐日志查询",
                    "诊断提示",
                    "Agent 使用提示",
                ],
            )
        ]

    return [("full_document", list(sections.keys()))]


def split_long_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """当语义块仍然过长时，按段落做兜底切分。"""
    if len(text) <= max_chars:
        return [text]

    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            overlap = current[-OVERLAP_CHARS:] if len(current) > OVERLAP_CHARS else current
            current = f"{overlap}\n\n{paragraph}"
        else:
            # 单个段落已经超过 max_chars，只能按字符兜底切开。
            for start in range(0, len(paragraph), max_chars - OVERLAP_CHARS):
                chunks.append(paragraph[start : start + max_chars])
            current = ""

    if current:
        chunks.append(current)

    return chunks


def build_chunk_metadata(
    record: dict[str, Any],
    chunk_index: int,
    chunk_role: str,
    content: str,
) -> dict[str, Any]:
    """生成 Milvus metadata 字段。

    你的项目 Milvus collection 里有 JSON metadata 字段，适合放这些可过滤字段。
    content 负责语义召回，metadata 负责后续筛选、展示、溯源。
    """
    metadata = dict(record.get("metadata", {}))
    metadata.update(
        {
            "_source": INPUT_JSONL_PATH.resolve().as_posix(),
            "_extension": ".jsonl",
            "_file_name": INPUT_JSONL_PATH.name,
            "source_record_id": record.get("id"),
            "chunk_index": chunk_index,
            "chunk_role": chunk_role,
            "chunk_chars": len(content),
        }
    )

    for key in (
        "doc_type",
        "alert_name",
        "category",
        "severity",
        "service_name",
        "service_role",
        "namespace",
        "owner",
        "log_topic",
        "metrics_job",
        "trigger",
    ):
        value = record.get(key)
        if value is not None:
            metadata[key] = value

    return metadata


def split_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    """把一条原始记录切成一个或多个 Milvus chunk。"""
    content = str(record.get("content", "")).strip()
    if not content:
        return []

    doc_type = record.get("doc_type") or record.get("metadata", {}).get("doc_type", "")
    title, sections = split_markdown_sections(content)
    prefix = build_context_prefix(record)

    chunks: list[dict[str, Any]] = []
    chunk_index = 1

    for chunk_role, headings in group_sections(doc_type, sections):
        section_texts = [sections[heading] for heading in headings if heading in sections]
        if not section_texts:
            continue

        chunk_content = "\n\n".join(part for part in [title, prefix, *section_texts] if part)

        for part in split_long_text(chunk_content):
            metadata = build_chunk_metadata(record, chunk_index, chunk_role, part)
            chunks.append(
                {
                    "id": f"{record.get('id')}-chunk-{chunk_index:02d}",
                    "content": part,
                    "metadata": metadata,
                }
            )
            chunk_index += 1

    if chunks:
        return chunks

    # 如果文档没有二级标题，就退回到整篇文档切分。
    for part in split_long_text(content):
        metadata = build_chunk_metadata(record, chunk_index, "full_document", part)
        chunks.append(
            {
                "id": f"{record.get('id')}-chunk-{chunk_index:02d}",
                "content": part,
                "metadata": metadata,
            }
        )
        chunk_index += 1

    return chunks


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """写出 JSONL 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    """执行切分，并打印切分统计。"""
    if not INPUT_JSONL_PATH.exists():
        raise FileNotFoundError(f"找不到输入文件，请先生成种子数据: {INPUT_JSONL_PATH}")

    source_records = load_jsonl(INPUT_JSONL_PATH)
    chunks: list[dict[str, Any]] = []

    for record in source_records:
        chunks.extend(split_record(record))

    write_jsonl(OUTPUT_CHUNKS_PATH, chunks)

    role_counter = Counter(chunk["metadata"]["chunk_role"] for chunk in chunks)
    type_counter = Counter(chunk["metadata"].get("doc_type", "") for chunk in chunks)
    lengths = [len(chunk["content"]) for chunk in chunks]

    print(f"原始记录数: {len(source_records)}")
    print(f"Milvus chunk 数: {len(chunks)}")
    print(f"输出文件: {OUTPUT_CHUNKS_PATH.resolve()}")
    print(f"按文档类型统计: {dict(type_counter)}")
    print(f"按 chunk_role 统计: {dict(role_counter)}")
    print(
        "chunk 长度统计: "
        f"min={min(lengths)}, max={max(lengths)}, avg={sum(lengths) // len(lengths)}"
    )


if __name__ == "__main__":
    main()
