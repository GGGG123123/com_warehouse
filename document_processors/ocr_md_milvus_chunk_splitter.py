"""把 OCR 识别后的 Markdown 文件切分成适合 Milvus 入库的 JSONL。

这个脚本处理的是“已经 OCR 完成”的 Markdown 文件。
也就是说:
    PDF 图片页 -> OCR -> Markdown
这一步已经完成，本脚本只负责:
    Markdown -> 语义 chunk -> JSONL

运行方式:
    直接运行本文件即可，不需要命令行参数。

    C:\\Users\\Administrator\\Desktop\\agent源代码\\super_biz_agent_py-release-2026-05-17\\.venv\\Scripts\\python.exe ^
        document_processors\\ocr_md_milvus_chunk_splitter.py

你只需要修改下面“输入输出配置”里的 INPUT_MD_PATH。

输出 JSONL 的每一行都是一个可入库 chunk:
    {
      "id": "ocrmd-demo-0001-a1b2c3d4",
      "content": "用于 embedding 的文本",
      "metadata": {
        "_source": "原始 md 文件路径",
        "doc_type": "ocr_markdown",
        "chunk_role": "text/table/code",
        "heading_path": "第一章 > 1.1 小节",
        "page_start": 3,
        "page_end": 4
      }
    }

为什么不直接按固定字数切:
    OCR 后的 Markdown 通常包含标题、表格、代码块、页码。
    如果只按 800 字硬切，容易把“一个表格”或“一个评分标准”切断。
    本脚本优先按 Markdown 标题、表格、代码块、段落切分，
    只有单个语义块过长时，才会二次按长度切。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
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

# OCR Markdown 文件存放目录。
OCR_MD_DIR = DATA_DIR / "ocr_md"

# 你把 OCR 后的 md 文件放到这里，然后修改这个路径即可。
# 默认使用本脚本附带的测试文档，方便你先确认流程能跑通。
INPUT_MD_PATH = OCR_MD_DIR / "ocr_pdf_demo.md"

# 切分后准备入 Milvus 的 JSONL。
OUTPUT_CHUNKS_PATH = OCR_MD_DIR / "ocr_md_milvus_chunks.jsonl"

# 文档身份信息。
# DOCUMENT_ID 会进入 chunk id 和 metadata，建议使用英文、数字、下划线。
DOCUMENT_ID = "ocr_pdf_demo"
DOCUMENT_TITLE = "OCR Markdown 文档示例"

# 单个 chunk 的推荐最大字符数。
# Milvus content 字段最大 8000，但 embedding/RAG 不适合太长。
# OCR 文档建议 1200-1600 字之间；这里取 1400。
MAX_CHARS = 1400

# 二次切分时保留的重叠字符，避免上下文断裂。
OVERLAP_CHARS = 120

# 如果某段太短，优先合并到相邻 chunk，减少碎片化召回。
MIN_CHARS = 180


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class MarkdownBlock:
    """Markdown 中的一个语义块。

    block_type:
        heading: 标题行
        table: Markdown 表格
        code: 代码块
        paragraph: 普通段落、列表、OCR 识别出来的连续文本

    heading_path:
        当前块所在的标题路径，例如:
        "表5 感知觉与社会参与指标和评分 > 社会交往能力"

    page_no:
        如果 OCR Markdown 里有页码标记，就记录当前块来自哪一页。
        没有页码时为 None。
    """

    block_type: str
    text: str
    heading_path: list[str]
    page_no: int | None


# =============================================================================
# 通用工具
# =============================================================================


def read_text(path: Path) -> str:
    """读取 Markdown 文件，并给出明确的错误提示。"""
    if not path.exists():
        raise FileNotFoundError(
            f"找不到 OCR Markdown 文件: {path}\n"
            "请把 OCR 后的 .md 文件放到 document_processors/data/ocr_md 目录，"
            "然后修改 INPUT_MD_PATH。"
        )

    return path.read_text(encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """把 chunk 列表写成 JSONL。

    JSONL 是“一行一个 JSON 对象”，适合后续逐行读取、批量 embedding、批量入库。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def normalize_markdown(text: str) -> str:
    """做轻量清洗，不破坏 Markdown 结构。

    OCR 结果里常见问题:
        1. Windows / Linux 换行混用；
        2. 行尾有很多空格；
        3. 连续空行过多；
        4. 全角冒号和半角冒号混杂。

    注意:
        这里不做激进的“智能纠错”，因为 OCR 内容可能是标准条款、代码、表格。
        过度清洗反而可能破坏原文。
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip()


def stable_hash(text: str, length: int = 8) -> str:
    """生成稳定短哈希，用于 chunk id 去重。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def safe_ascii_id(value: str) -> str:
    """把文档 ID 转成 Milvus 主键友好的 ASCII 字符串。

    Milvus 的 id 字段虽然是 VARCHAR，但为了减少兼容问题，
    主键最好只使用英文、数字、下划线和短横线。
    """
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = value.strip("-_")
    return value or "doc"


def detect_page_number(line: str) -> int | None:
    """从常见 OCR 页码标记中识别页码。

    支持示例:
        <!-- page: 3 -->
        <!-- Page 3 -->
        --- page 3 ---
        # 第 3 页
        第3页
    """
    patterns = (
        r"^\s*<!--\s*page\s*[:=]?\s*(\d+)\s*-->\s*$",
        r"^\s*-{2,}\s*page\s*(\d+)\s*-{2,}\s*$",
        r"^\s*#{1,6}\s*第\s*(\d+)\s*页\s*$",
        r"^\s*第\s*(\d+)\s*页\s*$",
    )

    for pattern in patterns:
        match = re.match(pattern, line, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def is_heading(line: str) -> bool:
    """判断是否是 Markdown 标题。"""
    return bool(re.match(r"^\s*#{1,6}\s+\S+", line))


def parse_heading(line: str) -> tuple[int, str]:
    """解析 Markdown 标题级别和标题文本。"""
    match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
    if not match:
        return 0, line.strip()
    return len(match.group(1)), match.group(2).strip()


def looks_like_table_line(line: str) -> bool:
    """粗略判断一行是否是 Markdown 表格行。

    OCR 工具导出的表格通常长这样:
        | 指标 | 4分 | 3分 | 2分 | 1分 | 0分 |
        | --- | --- | --- | --- | --- | --- |

    只要包含两个以上竖线，就先按表格处理。
    """
    return line.count("|") >= 2


def looks_like_table_separator(line: str) -> bool:
    """判断 Markdown 表格分隔行，例如 | --- | --- |。"""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return False

    body = stripped.strip("|").strip()
    return bool(body) and all(set(cell.strip()) <= {"-", ":"} for cell in body.split("|"))


# =============================================================================
# Markdown 解析
# =============================================================================


def parse_markdown_blocks(text: str) -> list[MarkdownBlock]:
    """把 Markdown 解析成语义块。

    解析策略:
        1. 标题单独成块，同时更新当前 heading_path；
        2. 代码块从 ``` 开始到 ``` 结束，整体保留；
        3. Markdown 表格连续行整体保留；
        4. 普通段落按空行分段；
        5. 页码标记不入 content，只进入 metadata。
    """
    lines = text.splitlines()
    blocks: list[MarkdownBlock] = []
    heading_stack: list[tuple[int, str]] = []
    current_page: int | None = None
    paragraph_lines: list[str] = []
    index = 0

    def current_heading_path() -> list[str]:
        return [heading for _, heading in heading_stack]

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        paragraph = "\n".join(paragraph_lines).strip()
        if paragraph:
            blocks.append(
                MarkdownBlock(
                    block_type="paragraph",
                    text=paragraph,
                    heading_path=current_heading_path(),
                    page_no=current_page,
                )
            )
        paragraph_lines = []

    while index < len(lines):
        line = lines[index]

        page_no = detect_page_number(line)
        if page_no is not None:
            flush_paragraph()
            current_page = page_no
            index += 1
            continue

        if is_heading(line):
            flush_paragraph()
            level, title = parse_heading(line)

            # 删除同级或更深级别标题，保留父级标题路径。
            heading_stack = [
                (existing_level, existing_title)
                for existing_level, existing_title in heading_stack
                if existing_level < level
            ]
            heading_stack.append((level, title))

            blocks.append(
                MarkdownBlock(
                    block_type="heading",
                    text=line.strip(),
                    heading_path=current_heading_path(),
                    page_no=current_page,
                )
            )
            index += 1
            continue

        if line.strip().startswith("```"):
            flush_paragraph()
            code_lines = [line]
            index += 1
            while index < len(lines):
                code_lines.append(lines[index])
                if lines[index].strip().startswith("```"):
                    index += 1
                    break
                index += 1

            blocks.append(
                MarkdownBlock(
                    block_type="code",
                    text="\n".join(code_lines).strip(),
                    heading_path=current_heading_path(),
                    page_no=current_page,
                )
            )
            continue

        if looks_like_table_line(line):
            flush_paragraph()
            table_lines = [line]
            index += 1
            while index < len(lines) and looks_like_table_line(lines[index]):
                table_lines.append(lines[index])
                index += 1

            blocks.append(
                MarkdownBlock(
                    block_type="table",
                    text="\n".join(table_lines).strip(),
                    heading_path=current_heading_path(),
                    page_no=current_page,
                )
            )
            continue

        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()
    return blocks


# =============================================================================
# 表格与评分标准处理
# =============================================================================


def markdown_table_to_search_text(table_text: str) -> str:
    """把 Markdown 表格转成更利于向量检索的行文本。

    为什么要转换:
        向量模型可以处理 Markdown 表格，但“列含义 + 单元格内容”展开后更好召回。

    例如:
        | 指标 | 4分 | 3分 |
        | --- | --- | --- |
        | 社会交往能力 | 能交往 | 被动接触 |

    会补充成:
        表格行1: 指标=社会交往能力；4分=能交往；3分=被动接触
    """
    lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    useful_lines = [line for line in lines if not looks_like_table_separator(line)]

    if len(useful_lines) < 2:
        return table_text

    header_cells = split_table_row(useful_lines[0])
    row_texts: list[str] = []

    for row_index, row_line in enumerate(useful_lines[1:], start=1):
        cells = split_table_row(row_line)
        pairs: list[str] = []

        for cell_index, cell in enumerate(cells):
            header = header_cells[cell_index] if cell_index < len(header_cells) else f"列{cell_index + 1}"
            if cell:
                pairs.append(f"{header}={cell}")

        if pairs:
            row_texts.append(f"表格行{row_index}: " + "；".join(pairs))

    if not row_texts:
        return table_text

    return "\n".join(row_texts)


def is_score_table(table_text: str) -> bool:
    """判断表格是否像“评分标准表”。

    只要表头里出现 0分、1分、2分、3分、4分 这类列名，
    就认为这张表适合按“每一行指标”切分。
    """
    lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    useful_lines = [line for line in lines if not looks_like_table_separator(line)]
    if len(useful_lines) < 2:
        return False

    headers = [header.replace(" ", "") for header in split_table_row(useful_lines[0])]
    score_header_count = sum(1 for header in headers if re.fullmatch(r"[0-9]分", header))
    return score_header_count >= 2


def split_score_table_rows(block: MarkdownBlock) -> list[MarkdownBlock]:
    """把评分表拆成“一行一个评分指标”的多个表格块。

    为什么要这么做:
        例如老年人能力评估规范中，一张表可能有多个评估指标。
        如果整张表作为一个 chunk，metadata["scores"]["4分"] 会混合多个指标的 4 分标准。
        按行切开后，一个 chunk 就对应一个评估指标，scores 结构也更干净。
    """
    lines = [line for line in block.text.splitlines() if line.strip()]
    if len(lines) <= 3:
        return [block]

    header_lines = lines[:2] if looks_like_table_separator(lines[1]) else lines[:1]
    data_lines = lines[len(header_lines) :]
    row_blocks: list[MarkdownBlock] = []

    for row_line in data_lines:
        if not looks_like_table_line(row_line):
            continue

        row_blocks.append(
            MarkdownBlock(
                block_type="table",
                text="\n".join(header_lines + [row_line]),
                heading_path=block.heading_path,
                page_no=block.page_no,
            )
        )

    return row_blocks or [block]


def split_table_row(row: str) -> list[str]:
    """把 Markdown 表格的一行拆成单元格。"""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def extract_score_map(text: str) -> dict[str, str]:
    """从文本里提取评分标准。

    你的老年人能力评估这类 PDF 很重视“0分、1分、2分...”。
    所以这里会尽量识别评分标准，并放入 metadata["scores"]。

    支持:
        4分: 能独立完成
        3 分：需要提醒
        | 指标 | 4分 | 3分 | 2分 | 1分 | 0分 |

    注意:
        这是规则提取，不保证覆盖所有 OCR 表格形态。
        但 content 里仍然保留原始表格，所以不会丢信息。
    """
    scores: dict[str, str] = {}

    # 普通行: 4分: xxx
    for match in re.finditer(r"(?m)^\s*([0-9])\s*分\s*[:：]\s*(.+?)\s*$", text):
        scores[f"{match.group(1)}分"] = match.group(2).strip()

    # 表格列: | 指标 | 4分 | 3分 | ...
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    table_lines = [line for line in lines if looks_like_table_line(line)]
    useful_lines = [line for line in table_lines if not looks_like_table_separator(line)]

    if len(useful_lines) >= 2:
        headers = split_table_row(useful_lines[0])
        score_columns = [
            (index, header.replace(" ", ""))
            for index, header in enumerate(headers)
            if re.fullmatch(r"[0-9]分", header.replace(" ", ""))
        ]

        for row_line in useful_lines[1:]:
            cells = split_table_row(row_line)
            for index, score_key in score_columns:
                if index < len(cells) and cells[index]:
                    # 如果同一分值出现多行，就用换行合并，避免覆盖。
                    old_value = scores.get(score_key)
                    new_value = cells[index].strip()
                    scores[score_key] = f"{old_value}\n{new_value}" if old_value else new_value

    return scores


def extract_single_table_row_fields(text: str) -> dict[str, str]:
    """从单行 Markdown 表格里提取结构化字段。

    如果评分表已经被 split_score_table_rows 拆成一行一个 chunk，
    这里就能拿到:
        一级指标 -> category
        评估指标 -> indicator
    这些字段后续可以用于过滤和展示。
    """
    lines = [line.strip() for line in text.splitlines() if looks_like_table_line(line)]
    useful_lines = [line for line in lines if not looks_like_table_separator(line)]
    if len(useful_lines) < 2:
        return {}

    headers = split_table_row(useful_lines[0])
    cells = split_table_row(useful_lines[1])
    fields: dict[str, str] = {}

    for index, header in enumerate(headers):
        if index >= len(cells):
            continue
        header = header.strip()
        cell = cells[index].strip()
        if header and cell:
            fields[header] = cell

    return fields


# =============================================================================
# chunk 构造
# =============================================================================


def build_context_prefix(blocks: list[MarkdownBlock]) -> str:
    """构造每个 chunk 都带的固定上下文。

    加前缀的原因:
        如果只切出一段“0分: 不能与人交往”，模型不知道它属于哪个文档、哪个章节。
        加上标题、来源文件、章节路径后，召回结果更容易回答准确。
    """
    heading_path = blocks[-1].heading_path if blocks else []
    page_numbers = [block.page_no for block in blocks if block.page_no is not None]

    lines = [
        f"文档ID: {DOCUMENT_ID}",
        f"文档标题: {DOCUMENT_TITLE}",
        f"来源文件: {INPUT_MD_PATH.name}",
    ]

    if heading_path:
        lines.append("章节路径: " + " > ".join(heading_path))

    if page_numbers:
        lines.append(f"页码: {min(page_numbers)}-{max(page_numbers)}")

    return "\n".join(lines)


def make_chunk_content(blocks: list[MarkdownBlock], role: str) -> str:
    """把一个或多个 MarkdownBlock 合成最终用于 embedding 的 content。"""
    prefix = build_context_prefix(blocks)
    body_parts: list[str] = []

    for block in blocks:
        if block.block_type == "table":
            body_parts.append("表格原文:\n" + block.text)
            body_parts.append("表格检索展开:\n" + markdown_table_to_search_text(block.text))
        else:
            body_parts.append(block.text)

    body = "\n\n".join(part.strip() for part in body_parts if part.strip())
    return f"{prefix}\n\nchunk类型: {role}\n\n{body}".strip()


def build_chunk_metadata(
    chunk_index: int,
    role: str,
    content: str,
    blocks: list[MarkdownBlock],
) -> dict[str, Any]:
    """构造 Milvus metadata 字段。

    metadata 不参与 embedding，但可以用于:
        1. 检索结果展示来源；
        2. 后续按 doc_type、chunk_role、页码过滤；
        3. 删除同一个来源文件的旧数据；
        4. 保存结构化评分 scores。
    """
    heading_path = blocks[-1].heading_path if blocks else []
    page_numbers = [block.page_no for block in blocks if block.page_no is not None]
    scores = extract_score_map(content)
    table_fields = extract_single_table_row_fields(content)

    metadata: dict[str, Any] = {
        "_source": INPUT_MD_PATH.resolve().as_posix(),
        "_extension": ".md",
        "_file_name": INPUT_MD_PATH.name,
        "source_type": "ocr_markdown",
        "doc_type": "ocr_markdown",
        "document_id": DOCUMENT_ID,
        "document_title": DOCUMENT_TITLE,
        "chunk_index": chunk_index,
        "chunk_role": role,
        "heading_path": " > ".join(heading_path),
        "heading": heading_path[-1] if heading_path else "",
        "content_length": len(content),
        "contains_table": any(block.block_type == "table" for block in blocks),
        "contains_code": any(block.block_type == "code" for block in blocks),
    }

    if page_numbers:
        metadata["page_start"] = min(page_numbers)
        metadata["page_end"] = max(page_numbers)

    if scores:
        metadata["scores"] = scores
        metadata["score_levels"] = sorted(scores.keys(), reverse=True)
        metadata["is_score_standard"] = True

    if table_fields:
        metadata["table_row_fields"] = table_fields

        # 常见业务字段做一层标准化，方便后续过滤检索。
        category = table_fields.get("一级指标") or table_fields.get("类别") or table_fields.get("分类")
        indicator = table_fields.get("评估指标") or table_fields.get("指标") or table_fields.get("项目")

        if category:
            metadata["category"] = category
        if indicator:
            metadata["indicator"] = indicator

    return metadata


def split_long_text_block(block: MarkdownBlock, max_chars: int = MAX_CHARS) -> list[MarkdownBlock]:
    """当单个普通段落或代码块过长时，按长度二次切分。

    表格不在这里处理，表格有单独的 split_large_table。
    """
    if len(block.text) <= max_chars:
        return [block]

    parts: list[MarkdownBlock] = []
    step = max_chars - OVERLAP_CHARS

    for start in range(0, len(block.text), step):
        text_part = block.text[start : start + max_chars].strip()
        if not text_part:
            continue
        parts.append(
            MarkdownBlock(
                block_type=block.block_type,
                text=text_part,
                heading_path=block.heading_path,
                page_no=block.page_no,
            )
        )

    return parts


def split_large_table(block: MarkdownBlock, max_chars: int = MAX_CHARS) -> list[MarkdownBlock]:
    """把过长 Markdown 表格按行切分，并保留表头。

    这样可以避免一个大表超过 chunk 长度，同时每个子表仍然知道列名。
    """
    if len(block.text) <= max_chars:
        return [block]

    lines = [line for line in block.text.splitlines() if line.strip()]
    if len(lines) <= 3:
        return split_long_text_block(block, max_chars)

    header_lines = lines[:2] if looks_like_table_separator(lines[1]) else lines[:1]
    data_lines = lines[len(header_lines) :]

    parts: list[MarkdownBlock] = []
    current_lines = list(header_lines)

    for line in data_lines:
        candidate = "\n".join(current_lines + [line])
        if len(candidate) > max_chars and len(current_lines) > len(header_lines):
            parts.append(
                MarkdownBlock(
                    block_type="table",
                    text="\n".join(current_lines),
                    heading_path=block.heading_path,
                    page_no=block.page_no,
                )
            )
            current_lines = list(header_lines)

        current_lines.append(line)

    if len(current_lines) > len(header_lines):
        parts.append(
            MarkdownBlock(
                block_type="table",
                text="\n".join(current_lines),
                heading_path=block.heading_path,
                page_no=block.page_no,
            )
        )

    return parts


def flush_text_chunk(
    chunks: list[dict[str, Any]],
    pending_blocks: list[MarkdownBlock],
    chunk_index: int,
) -> int:
    """把累积的普通文本块写成一个 chunk。"""
    if not pending_blocks:
        return chunk_index

    content = make_chunk_content(pending_blocks, "text")
    metadata = build_chunk_metadata(chunk_index, "text", content, pending_blocks)
    chunk_id = build_chunk_id(chunk_index, content)

    chunks.append({"id": chunk_id, "content": content, "metadata": metadata})
    return chunk_index + 1


def build_chunk_id(chunk_index: int, content: str) -> str:
    """生成不超过 100 字符的 Milvus 主键。"""
    doc_id = safe_ascii_id(DOCUMENT_ID)[:36]
    return f"ocrmd-{doc_id}-{chunk_index:04d}-{stable_hash(content)}"


def split_markdown_to_chunks(text: str) -> list[dict[str, Any]]:
    """主切分函数。

    切分规则:
        1. 表格单独成 chunk，因为表格通常是一组完整知识；
        2. 代码块单独成 chunk，因为代码上下文不能和普通段落混在一起；
        3. 普通段落在同一标题路径下合并，直到接近 MAX_CHARS；
        4. 切换标题路径时，先把上一节内容输出；
        5. 过长内容再二次切分。
    """
    blocks = parse_markdown_blocks(normalize_markdown(text))
    chunks: list[dict[str, Any]] = []
    pending_blocks: list[MarkdownBlock] = []
    chunk_index = 1

    def pending_text() -> str:
        return make_chunk_content(pending_blocks, "text") if pending_blocks else ""

    for raw_block in blocks:
        if raw_block.block_type == "table" and is_score_table(raw_block.text):
            expanded_blocks = split_score_table_rows(raw_block)
        elif raw_block.block_type == "table":
            expanded_blocks = split_large_table(raw_block)
        else:
            expanded_blocks = split_long_text_block(raw_block)

        for block in expanded_blocks:
            if block.block_type in {"table", "code"}:
                chunk_index = flush_text_chunk(chunks, pending_blocks, chunk_index)
                pending_blocks = []

                role = block.block_type
                content = make_chunk_content([block], role)
                metadata = build_chunk_metadata(chunk_index, role, content, [block])
                chunks.append(
                    {
                        "id": build_chunk_id(chunk_index, content),
                        "content": content,
                        "metadata": metadata,
                    }
                )
                chunk_index += 1
                continue

            # 标题行只用于增强当前章节语义，不单独入库。
            # 它会和后面的段落一起组成 text chunk。
            same_section = (
                not pending_blocks
                or pending_blocks[-1].heading_path == block.heading_path
            )

            candidate_blocks = pending_blocks + [block]
            candidate_text = make_chunk_content(candidate_blocks, "text")

            should_flush = (
                pending_blocks
                and (
                    not same_section
                    or len(candidate_text) > MAX_CHARS
                    and len(pending_text()) >= MIN_CHARS
                )
            )

            if should_flush:
                chunk_index = flush_text_chunk(chunks, pending_blocks, chunk_index)
                pending_blocks = [block]
            else:
                pending_blocks.append(block)

    chunk_index = flush_text_chunk(chunks, pending_blocks, chunk_index)

    return chunks


# =============================================================================
# 脚本入口
# =============================================================================


def main() -> None:
    """执行 OCR Markdown 切分，并打印统计信息。"""
    markdown_text = read_text(INPUT_MD_PATH)
    chunks = split_markdown_to_chunks(markdown_text)

    if not chunks:
        raise ValueError("没有生成任何 chunk，请检查 OCR Markdown 是否为空")

    write_jsonl(OUTPUT_CHUNKS_PATH, chunks)

    role_counter = Counter(chunk["metadata"]["chunk_role"] for chunk in chunks)
    lengths = [len(chunk["content"]) for chunk in chunks]
    score_chunks = sum(1 for chunk in chunks if chunk["metadata"].get("scores"))

    print("OCR Markdown chunk 切分完成")
    print(f"输入文件: {INPUT_MD_PATH}")
    print(f"输出文件: {OUTPUT_CHUNKS_PATH}")
    print(f"chunk 数: {len(chunks)}")
    print(f"按 chunk_role 统计: {dict(role_counter)}")
    print(
        "chunk 长度统计: "
        f"min={min(lengths)}, max={max(lengths)}, avg={sum(lengths) // len(lengths)}"
    )
    print(f"识别到评分标准的 chunk 数: {score_chunks}")


if __name__ == "__main__":
    main()
