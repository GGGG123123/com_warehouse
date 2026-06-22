"""AIOps 运维知识数据切分脚本，输出适合 Milvus 向量库入库的 JSONL。

这个文件放在 document_processors 目录下，方便和 PDF、Markdown 等文档处理代码统一管理。

使用方式:
    直接运行本文件即可，不需要命令行参数。

    python document_processors/aiops_milvus_chunk_splitter.py

你只需要在下面的“输入输出配置”里改路径:
    INPUT_JSONL_PATH: 原始 AIOps JSONL 数据
    OUTPUT_CHUNKS_PATH: 切分后的 Milvus chunks JSONL

输出的每一行都是一个可入库 chunk:
    {
      "id": "唯一 chunk id",
      "content": "用于 embedding 的文本",
      "metadata": {
        "doc_type": "aiops_runbook",
        "alert_name": "HighCPUUsage",
        "service_name": "api-gateway",
        ...
      }
    }

注意:
    本脚本只做切分，不连接 Milvus，不调用 embedding。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


# =============================================================================
# 输入输出配置
# =============================================================================

# 当前文件所在目录:
# C:\Users\Administrator\Desktop\agent源代码\super_biz_agent_py-release-2026-05-17\document_processors
CURRENT_DIR = Path(__file__).resolve().parent

# document_processors/data 目录。
# 这样无论你从项目根目录运行，还是从 document_processors 目录运行，路径都不会乱。
DATA_DIR = CURRENT_DIR / "data"

# 原始结构化运维知识数据。
# 每一行是一条完整文档，例如一条 runbook、一条故障案例、一条告警规则。
INPUT_JSONL_PATH = DATA_DIR / "aiops_seed" / "aiops_seed_records.jsonl"

# 切分后的 Milvus 预入库文件。
# 每一行是一个 chunk，后续可以把 content 做 embedding，把 metadata 写入 Milvus JSON 字段。
OUTPUT_CHUNKS_PATH = DATA_DIR / "aiops_seed" / "aiops_seed_milvus_chunks.jsonl"

# 单个 chunk 的最大字符数。
# 你的项目 app/config.py 里 chunk_max_size 是 800，
# 但当前 DocumentSplitterService 二次切分用了 1600。
# 这里取 1400，是为了让每个 chunk 内容完整，同时不要太长。
MAX_CHARS = 1400

# 如果某个语义块超过 MAX_CHARS，就按段落继续切分。
# overlap 用于保留一点上下文，避免上一段和下一段完全断开。
OVERLAP_CHARS = 100


# =============================================================================
# JSONL 读取与写出
# =============================================================================


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 文件。

    JSONL 的特点是一行一个 JSON 对象，非常适合保存大量结构化文档。
    这里会逐行读取，任何一行 JSON 格式错误都会抛出明确的行号。
    """
    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            text = line.strip()

            # 跳过空行，避免因为文件末尾空白导致解析失败。
            if not text:
                continue

            try:
                records.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL 第 {line_no} 行解析失败: {exc}") from exc

    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """把切分后的 chunk 写出为 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


# =============================================================================
# Markdown 结构解析
# =============================================================================


def split_markdown_sections(content: str) -> tuple[str, dict[str, str]]:
    """把 Markdown 文档拆成一级标题和多个二级标题 section。

    例如原始文档中有:
        # api-gateway - HighCPUUsage 运维处置知识
        ## 元数据
        ## 触发条件
        ## 症状描述

    返回:
        title:
            一级标题，用于放进每个 chunk，增强召回上下文。

        sections:
            key 是二级标题名，例如 "触发条件"。
            value 是该二级标题及其正文，例如 "## 触发条件\n\nCPU 使用率连续 5 分钟超过 85%"。
    """
    lines = content.splitlines()
    title = ""
    sections: dict[str, list[str]] = {}
    current_heading = ""

    for line in lines:
        # 只把第一个 "# " 当作文档标题。
        if line.startswith("# ") and not title:
            title = line.strip()
            continue

        # 遇到 "## " 时，开始一个新的 section。
        if line.startswith("## "):
            current_heading = line.removeprefix("## ").strip()
            sections[current_heading] = [line]
            continue

        # 普通正文追加到当前 section。
        if current_heading:
            sections[current_heading].append(line)

    # 把每个 section 的多行内容合并成字符串，并去掉首尾空白。
    joined_sections = {
        heading: "\n".join(section_lines).strip()
        for heading, section_lines in sections.items()
    }

    return title, joined_sections


# =============================================================================
# 语义切分规则
# =============================================================================


def build_context_prefix(record: dict[str, Any]) -> str:
    """为每个 chunk 构造固定上下文前缀。

    为什么要加这个前缀:
        如果只把 "立即处置" 单独切出来，里面可能没有服务名、告警名、级别。
        用户问 "api-gateway CPU 高怎么处理" 时，向量检索就可能召回不准。

    所以每个 chunk 都补充:
        文档ID、数据类型、告警名称、分类、级别、服务名、责任团队、触发条件。
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

    # 过滤掉值为空的行，避免 content 里出现 "责任团队: " 这种无意义文本。
    return "\n".join(line for line in lines if not line.endswith(": "))


def group_sections(doc_type: str, sections: dict[str, str]) -> list[tuple[str, list[str]]]:
    """根据文档类型，把多个 Markdown section 组合成业务语义 chunk。

    这里是关键:
        不建议直接按字符硬切，因为运维知识有天然结构。
        比如 runbook 里 "常见根因 + 立即处置 + 诊断步骤" 应该放在一起，
        用户问怎么处理故障时，这些内容一起召回才有用。
    """
    if doc_type == "aiops_runbook":
        return [
            # 概览块: 适合回答“这个告警是什么、怎么触发、看什么指标/日志”。
            ("overview", ["元数据", "触发条件", "症状描述", "推荐 PromQL", "推荐日志查询"]),
            # 诊断处置块: 适合回答“为什么发生、应该怎么处理、怎么排查”。
            ("diagnosis", ["常见根因", "立即处置", "诊断步骤"]),
            # 验证预防块: 适合回答“怎么确认恢复、以后怎么避免”。
            ("verification", ["验证标准", "预防措施", "Agent 使用提示"]),
        ]

    if doc_type == "aiops_incident_case":
        return [
            # 证据块: 适合回答“这个故障有什么现象、证据是什么、根因是什么”。
            ("incident_evidence", ["元数据", "事件摘要", "关键证据", "根因判断"]),
            # 恢复块: 适合回答“当时怎么处理、如何恢复、复盘看什么”。
            ("incident_resolution", ["处置过程", "恢复验证", "复盘关注点"]),
        ]

    if doc_type == "aiops_alert_rule":
        return [
            # 告警规则通常较短，保持一块即可。
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

    # 兜底逻辑: 如果未来有新的 doc_type，就先按已有 section 合成整篇文档。
    return [("full_document", list(sections.keys()))]


def split_long_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """把过长的文本按段落继续切分。

    正常情况下，前面的业务语义切分已经足够短。
    只有当某个 chunk 超过 MAX_CHARS 时，才会进入这里。
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"

        # 如果加入当前段落后还没超长，就继续累积。
        if len(candidate) <= max_chars:
            current = candidate
            continue

        # 如果已经超长，把当前 chunk 保存下来，再开启新 chunk。
        if current:
            chunks.append(current)

            # 保留上一块末尾少量字符，让下一块带一点上下文。
            overlap = current[-OVERLAP_CHARS:] if len(current) > OVERLAP_CHARS else current
            current = f"{overlap}\n\n{paragraph}"
            continue

        # 如果单个段落本身就超过 max_chars，只能按字符硬切。
        step = max_chars - OVERLAP_CHARS
        for start in range(0, len(paragraph), step):
            chunks.append(paragraph[start : start + max_chars])
        current = ""

    if current:
        chunks.append(current)

    return chunks


# =============================================================================
# chunk 构建
# =============================================================================


def build_chunk_metadata(
    record: dict[str, Any],
    chunk_index: int,
    chunk_role: str,
    content: str,
) -> dict[str, Any]:
    """构造写入 Milvus metadata 字段的数据。

    在你的项目里，Milvus 配置如下:
        text_field="content"
        vector_field="vector"
        primary_field="id"
        metadata_field="metadata"

    所以:
        content 负责语义检索。
        metadata 负责结构化过滤、展示和溯源。
    """
    metadata = dict(record.get("metadata", {}))

    # 这些下划线字段兼容你项目现有的 delete_by_source 逻辑。
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

    # 把常用过滤字段也放进 metadata。
    # 后续可以按告警名、服务名、严重级别、团队等条件过滤检索。
    filter_keys = (
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
    )

    for key in filter_keys:
        value = record.get(key)
        if value is not None:
            metadata[key] = value

    return metadata


def split_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    """把一条原始 AIOps 记录切成一个或多个 Milvus chunk。"""
    content = str(record.get("content", "")).strip()
    if not content:
        return []

    doc_type = record.get("doc_type") or record.get("metadata", {}).get("doc_type", "")
    title, sections = split_markdown_sections(content)
    prefix = build_context_prefix(record)

    chunks: list[dict[str, Any]] = []
    chunk_index = 1

    # 先按业务语义组合 section。
    for chunk_role, headings in group_sections(doc_type, sections):
        section_texts = [sections[heading] for heading in headings if heading in sections]
        if not section_texts:
            continue

        # 每个 chunk 都带 title 和 prefix，保证任何单块被召回时都有完整上下文。
        chunk_content = "\n\n".join(part for part in [title, prefix, *section_texts] if part)

        # 如果该语义块仍然过长，再按段落二次切分。
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

    # 如果文档没有标准 Markdown 二级标题，就退回到整篇文档切分。
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


# =============================================================================
# 主流程
# =============================================================================


def main() -> None:
    """执行切分，并打印统计结果。"""
    if not INPUT_JSONL_PATH.exists():
        raise FileNotFoundError(f"找不到输入文件: {INPUT_JSONL_PATH}")

    source_records = load_jsonl(INPUT_JSONL_PATH)
    chunks: list[dict[str, Any]] = []

    for record in source_records:
        chunks.extend(split_record(record))

    if not chunks:
        raise ValueError("没有生成任何 chunk，请检查输入 JSONL 的 content 字段")

    write_jsonl(OUTPUT_CHUNKS_PATH, chunks)

    # 打印统计信息，方便你判断切分是否合理。
    role_counter = Counter(chunk["metadata"]["chunk_role"] for chunk in chunks)
    type_counter = Counter(chunk["metadata"].get("doc_type", "") for chunk in chunks)
    lengths = [len(chunk["content"]) for chunk in chunks]

    print("AIOps Milvus chunk 切分完成")
    print(f"输入文件: {INPUT_JSONL_PATH}")
    print(f"输出文件: {OUTPUT_CHUNKS_PATH}")
    print(f"原始记录数: {len(source_records)}")
    print(f"Milvus chunk 数: {len(chunks)}")
    print(f"按文档类型统计: {dict(type_counter)}")
    print(f"按 chunk_role 统计: {dict(role_counter)}")
    print(
        "chunk 长度统计: "
        f"min={min(lengths)}, max={max(lengths)}, avg={sum(lengths) // len(lengths)}"
    )


if __name__ == "__main__":
    main()
