"""把 AIOps Markdown 运维文档整理成“未切分”的 JSONL 原始数据。

这个脚本解决的问题:
    你现在可能只有很多 Markdown 文档，还没有切分前的 JSONL 文件。
    那么可以先运行本脚本，把 Markdown 统一整理成 aiops_seed_records.jsonl。

完整流程:
    第一步: Markdown 文档 -> 未切分 JSONL
        python document_processors/aiops_jsonl_builder.py

    第二步: 未切分 JSONL -> Milvus chunks JSONL
        python document_processors/aiops_milvus_chunk_splitter.py

输出文件结构:
    {
      "id": "原始文档ID",
      "doc_type": "aiops_runbook",
      "alert_name": "HighCPUUsage",
      "category": "资源异常",
      "severity": "critical",
      "service_name": "api-gateway",
      "content": "完整 Markdown 正文，暂时不切分",
      "metadata": {
        "source": "aiops_jsonl_builder",
        "doc_type": "aiops_runbook",
        "alert_name": "HighCPUUsage",
        ...
      }
    }

注意:
    本脚本只生成“未切分 JSONL”，不做 embedding，不连接 Milvus。
"""

from __future__ import annotations

import json
import re
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
DATA_DIR = CURRENT_DIR / "data"

# Markdown 原始文档目录。
# 你把要整理的 .md 运维文档放到这个目录下即可。
INPUT_MARKDOWN_DIR = DATA_DIR / "aiops_seed" / "generated_docs"

# 未切分 JSONL 输出文件。
# 这个文件就是 aiops_milvus_chunk_splitter.py 的输入。
OUTPUT_JSONL_PATH = DATA_DIR / "aiops_seed" / "aiops_seed_records.jsonl"


# =============================================================================
# 字段映射配置
# =============================================================================

# Markdown 元数据里是中文字段名，这里映射成程序更容易处理的英文字段。
# 例如 Markdown 里:
#   - 告警名称: `HighCPUUsage`
# 会被转换成:
#   alert_name = "HighCPUUsage"
METADATA_KEY_MAP = {
    "文档ID": "doc_id",
    "数据类型": "doc_type",
    "告警名称": "alert_name",
    "告警分类": "category",
    "告警级别": "severity",
    "服务名称": "service_name",
    "受影响服务": "service_name",
    "服务角色": "service_role",
    "命名空间": "namespace",
    "责任团队": "owner",
    "日志主题": "log_topic",
    "指标 Job": "metrics_job",
    "指标Job": "metrics_job",
}


# =============================================================================
# Markdown 解析函数
# =============================================================================


def read_markdown(path: Path) -> str:
    """读取单个 Markdown 文件内容。"""
    return path.read_text(encoding="utf-8").strip()


def extract_title(content: str) -> str:
    """提取 Markdown 一级标题。

    一级标题通常是文档第一行，例如:
        # api-gateway - HighCPUUsage 运维处置知识

    如果文档没有一级标题，就返回空字符串。
    """
    for line in content.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return ""


def split_markdown_sections(content: str) -> dict[str, str]:
    """按二级标题拆分 Markdown 文档。

    返回示例:
        {
          "元数据": "## 元数据\n\n- 文档ID: ...",
          "触发条件": "## 触发条件\n\nCPU 使用率连续 5 分钟超过 85%",
          "症状描述": "## 症状描述\n\n实例负载升高..."
        }
    """
    sections: dict[str, list[str]] = {}
    current_heading = ""

    for line in content.splitlines():
        if line.startswith("## "):
            current_heading = line.removeprefix("## ").strip()
            sections[current_heading] = [line]
            continue

        if current_heading:
            sections[current_heading].append(line)

    return {
        heading: "\n".join(lines).strip()
        for heading, lines in sections.items()
    }


def clean_metadata_value(value: str) -> str:
    """清洗 Markdown 元数据值。

    Markdown 里很多值会写成:
        `HighCPUUsage`

    这里会去掉反引号、普通引号和多余空白。
    """
    cleaned = value.strip()
    cleaned = cleaned.strip("`")
    cleaned = cleaned.strip('"')
    cleaned = cleaned.strip("'")
    return cleaned.strip()


def parse_metadata_section(section_text: str) -> dict[str, str]:
    """解析 Markdown 的“元数据”section。

    支持的行格式:
        - 文档ID: `AIOPS-0001-high_cpu-api-gateway`
        - 告警名称: `HighCPUUsage`
        - 告警级别: `critical`

    不在 METADATA_KEY_MAP 里的字段会被忽略。
    """
    metadata: dict[str, str] = {}

    for line in section_text.splitlines():
        # 匹配 "- 字段名: 字段值" 或 "- 字段名：字段值"。
        match = re.match(r"^\s*[-*]\s*(.+?)\s*[:：]\s*(.+?)\s*$", line)
        if not match:
            continue

        raw_key = match.group(1).strip()
        raw_value = match.group(2).strip()
        normalized_key = METADATA_KEY_MAP.get(raw_key)

        if not normalized_key:
            continue

        metadata[normalized_key] = clean_metadata_value(raw_value)

    return metadata


def extract_plain_section_text(section_text: str) -> str:
    """提取 section 里的正文文本。

    这个函数会跳过标题行和空行，返回第一段真正的内容。
    主要用于提取“触发条件”。
    """
    lines: list[str] = []

    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            continue
        lines.append(stripped)

    return "\n".join(lines).strip()


def infer_doc_type(path: Path, metadata: dict[str, str]) -> str:
    """推断文档类型。

    优先使用 Markdown 元数据里的“数据类型”。
    如果没有，就根据文件名判断:
        *_runbook_*      -> aiops_runbook
        *_incident_*     -> aiops_incident_case
        *_alert_rule_*   -> aiops_alert_rule
    """
    doc_type = metadata.get("doc_type")
    if doc_type:
        return doc_type

    file_name = path.name.lower()
    if "_runbook_" in file_name:
        return "aiops_runbook"
    if "_incident_" in file_name:
        return "aiops_incident_case"
    if "_alert_rule_" in file_name:
        return "aiops_alert_rule"

    return "aiops_document"


def build_record_id(path: Path, metadata: dict[str, str], doc_type: str) -> str:
    """生成原始 JSONL 记录 ID。

    优先使用 Markdown 元数据里的“文档ID”。
    如果没有，就根据文件名生成一个稳定 ID。
    """
    doc_id = metadata.get("doc_id")
    if doc_id:
        return doc_id

    # 文件名本身通常已经包含编号、类型、场景、服务名。
    # 例如: 0001_runbook_high_cpu_api-gateway.md
    return f"{doc_type}-{path.stem}"


def extract_trigger(sections: dict[str, str], content: str) -> str:
    """提取触发条件。

    runbook 和 alert_rule 通常都有“## 触发条件”。
    incident 文档可能在“事件摘要”里写“触发条件为：xxx”，这里也做兜底提取。
    """
    trigger_section = sections.get("触发条件")
    if trigger_section:
        return extract_plain_section_text(trigger_section)

    # 兜底: 从整篇文本中尝试匹配“触发条件为：...”。
    match = re.search(r"触发条件为[:：](.+?)[。.\n]", content)
    if match:
        return match.group(1).strip()

    return ""


# =============================================================================
# JSONL 记录构建
# =============================================================================


def build_record_from_markdown(path: Path) -> dict[str, Any]:
    """把单个 Markdown 文件转换成一条未切分 JSONL 记录。"""
    content = read_markdown(path)
    title = extract_title(content)
    sections = split_markdown_sections(content)
    parsed_metadata = parse_metadata_section(sections.get("元数据", ""))

    doc_type = infer_doc_type(path, parsed_metadata)
    record_id = build_record_id(path, parsed_metadata, doc_type)
    trigger = extract_trigger(sections, content)

    # 这些字段放在顶层，是为了后续切分、过滤、调试更方便。
    record = {
        "id": record_id,
        "doc_type": doc_type,
        "alert_name": parsed_metadata.get("alert_name", ""),
        "category": parsed_metadata.get("category", ""),
        "severity": parsed_metadata.get("severity", ""),
        "service_name": parsed_metadata.get("service_name", ""),
        "service_role": parsed_metadata.get("service_role", ""),
        "namespace": parsed_metadata.get("namespace", ""),
        "owner": parsed_metadata.get("owner", ""),
        "log_topic": parsed_metadata.get("log_topic", ""),
        "metrics_job": parsed_metadata.get("metrics_job", ""),
        "trigger": trigger,
        # content 保留完整 Markdown，注意这里还没有切分。
        "content": content,
    }

    # metadata 适合未来写入 Milvus 的 metadata JSON 字段。
    record["metadata"] = {
        "source": "aiops_jsonl_builder",
        "source_file": path.resolve().as_posix(),
        "file_name": path.name,
        "title": title,
        "doc_type": doc_type,
        "alert_name": record["alert_name"],
        "category": record["category"],
        "severity": record["severity"],
        "service_name": record["service_name"],
        "service_role": record["service_role"],
        "namespace": record["namespace"],
        "owner": record["owner"],
    }

    # 去掉值为空的 metadata 字段，让 JSON 更干净。
    record["metadata"] = {
        key: value
        for key, value in record["metadata"].items()
        if value not in ("", None)
    }

    return record


def collect_markdown_files(markdown_dir: Path) -> list[Path]:
    """收集需要转换的 Markdown 文件。"""
    if not markdown_dir.exists():
        raise FileNotFoundError(f"Markdown 目录不存在: {markdown_dir}")

    files = sorted(
        path
        for path in markdown_dir.glob("*.md")
        if path.name.lower() != "readme.md"
    )

    if not files:
        raise FileNotFoundError(f"Markdown 目录中没有找到 .md 文件: {markdown_dir}")

    return files


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """写出未切分 JSONL 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


# =============================================================================
# 主流程
# =============================================================================


def main() -> None:
    """执行 Markdown 到未切分 JSONL 的转换。"""
    markdown_files = collect_markdown_files(INPUT_MARKDOWN_DIR)
    records = [build_record_from_markdown(path) for path in markdown_files]

    write_jsonl(OUTPUT_JSONL_PATH, records)

    doc_type_counter = Counter(record["doc_type"] for record in records)
    severity_counter = Counter(record["severity"] for record in records if record["severity"])

    print("AIOps 未切分 JSONL 生成完成")
    print(f"Markdown 输入目录: {INPUT_MARKDOWN_DIR}")
    print(f"JSONL 输出文件: {OUTPUT_JSONL_PATH}")
    print(f"Markdown 文件数: {len(markdown_files)}")
    print(f"JSONL 记录数: {len(records)}")
    print(f"按文档类型统计: {dict(doc_type_counter)}")
    print(f"按告警级别统计: {dict(severity_counter)}")


if __name__ == "__main__":
    main()
