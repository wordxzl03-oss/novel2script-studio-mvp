from __future__ import annotations

from dataclasses import dataclass
import re


class ChapterSplitError(ValueError):
    """Raised when novel text cannot be split into the required chapter structure."""


@dataclass(frozen=True)
class SplitChapter:
    """A parsed chapter from plain novel text. Deterministic, no LLM calls."""

    chapter_id: str
    index: int
    title: str
    content: str
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    para_count: int

    def paragraphs(self) -> list[str]:
        """Paragraph list. 1-based index of this list is THE contract that
        scene.source.para_range refers to (used by tracing UI and Linter)."""
        return split_paragraphs(self.content)

    def to_registry_item(self) -> dict[str, str]:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "summary": make_preview_summary(self.content),
        }


_CN_NUM = "零〇一二两三四五六七八九十百千万"

# 章标题。注意标题与编号之间允许无分隔（"第一章雨夜来信"是网文常见排版）。
_CHAPTER_HEADING_RE = re.compile(
    rf"""^\s*(?:
        第[{_CN_NUM}\d]+[章节回](?:[\s:：、.．·\-—]*\S.{{0,58}})?
        |
        chapter\s+\d+(?:[\s:：.\-]+.{{0,58}})?
        |
        \d{{1,3}}[\.、]\s*\S.{{0,58}}
    )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# 卷/部/幕是分卷分隔行而非章：单独成行且其后紧跟章标题、自身无正文，
# 若按章处理会因"无内容"导致整本书解析失败。
_SECTION_DIVIDER_RE = re.compile(
    rf"^\s*第[{_CN_NUM}\d]+[卷部幕](?:[\s:：、.．·\-—]*.{{0,58}})?\s*$"
)

# 标题行应当是短行；超过该长度的行更可能是以"第X章"开头的叙述句。
_MAX_HEADING_LENGTH = 60


def normalize_text(text: str) -> str:
    """Normalize line endings, strip BOM and trailing spaces; keep paragraph
    breaks because paragraph ranges are later used for source tracing."""
    if text is None:
        raise ChapterSplitError("Input text cannot be None.")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.lstrip("\ufeff")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    return normalized.strip()


def is_section_divider(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LENGTH:
        return False
    return bool(_SECTION_DIVIDER_RE.match(stripped))


def is_chapter_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LENGTH:
        return False
    if _SECTION_DIVIDER_RE.match(stripped):
        return False
    return bool(_CHAPTER_HEADING_RE.match(stripped))


def split_paragraphs(content: str) -> list[str]:
    """Split chapter content into paragraphs.

    兼容两种主流排版：
    1) 段落之间有空行；
    2) 网文 txt 常见的"一行一段、无空行"。
    若按空行只切出一个块、但块内仍有多行，则回退为按行分段。
    """
    stripped = content.strip()
    if not stripped:
        return []
    blocks = [p.strip() for p in re.split(r"\n\s*\n", stripped) if p.strip()]
    if len(blocks) <= 1:
        lines = [l.strip() for l in stripped.split("\n") if l.strip()]
        if len(lines) > 1:
            return lines
    return blocks


def count_paragraphs(content: str) -> int:
    return len(split_paragraphs(content))


def make_preview_summary(content: str, max_length: int = 120) -> str:
    """Deterministic preview placeholder; not a semantic LLM summary."""
    compact = re.sub(r"\s+", " ", content).strip()
    if len(compact) <= max_length:
        return compact
    return compact[:max_length].rstrip() + "..."


def _line_records(text: str) -> list[tuple[int, str, int, int]]:
    """Return records as (line_number, raw_line, start_char, end_char)."""
    records: list[tuple[int, str, int, int]] = []
    offset = 0
    for line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        records.append((line_number, raw_line, offset, offset + len(raw_line)))
        offset += len(raw_line)
    return records


def _strip_empty_edge_lines(records):
    start = 0
    end = len(records)
    while start < end and not records[start][1].strip():
        start += 1
    while end > start and not records[end - 1][1].strip():
        end -= 1
    return records[start:end]


def split_chapters(text: str, min_chapters: int = 1) -> list[SplitChapter]:
    """Split plain novel text into chapters with deterministic ids CH001, CH002...

    行为约定：
    - 第一个章标题之前的内容（书名、作者、楔子等）会被丢弃；
    - 分卷行（第X卷/部/幕）会被跳过，不计为章，也不混入正文；
    - 识别出的标题若无正文（如目录残留），跳过该标题而不是让整本书解析失败。
    """
    normalized = normalize_text(text)
    if not normalized:
        raise ChapterSplitError("Input text is empty.")
    if min_chapters < 1:
        raise ChapterSplitError("min_chapters must be greater than or equal to 1.")

    records = _line_records(normalized)
    heading_positions = [
        i for i, (_, raw_line, _, _) in enumerate(records) if is_chapter_heading(raw_line)
    ]

    if not heading_positions:
        if min_chapters > 1:
            raise ChapterSplitError(
                f"No chapter headings detected. Expected at least {min_chapters} chapters."
            )
        content = normalized.strip()
        return [
            SplitChapter(
                chapter_id="CH001", index=1, title="正文", content=content,
                start_line=1, end_line=records[-1][0],
                start_char=0, end_char=len(normalized),
                para_count=count_paragraphs(content),
            )
        ]

    raw_chapters: list[tuple[str, str, int, int, int, int]] = []
    for pos_index, heading_record_index in enumerate(heading_positions):
        next_heading_record_index = (
            heading_positions[pos_index + 1]
            if pos_index + 1 < len(heading_positions)
            else len(records)
        )
        heading_line_number, heading_line, heading_start, _ = records[heading_record_index]
        title = heading_line.strip()

        content_records = records[heading_record_index + 1 : next_heading_record_index]
        content_records = [r for r in content_records if not is_section_divider(r[1])]
        content_records = _strip_empty_edge_lines(content_records)
        if not content_records:
            continue  # 空内容标题：跳过，不让整本书解析失败

        content = "".join(raw_line for _, raw_line, _, _ in content_records).strip()
        raw_chapters.append(
            (
                title, content, heading_line_number,
                content_records[-1][0], heading_start, content_records[-1][3],
            )
        )

    if len(raw_chapters) < min_chapters:
        raise ChapterSplitError(
            f"Detected {len(raw_chapters)} chapters, expected at least {min_chapters}."
        )

    return [
        SplitChapter(
            chapter_id=f"CH{index:03d}", index=index, title=title, content=content,
            start_line=start_line, end_line=end_line,
            start_char=start_char, end_char=end_char,
            para_count=count_paragraphs(content),
        )
        for index, (title, content, start_line, end_line, start_char, end_char) in enumerate(
            raw_chapters, start=1
        )
    ]


def build_chapter_registry(chapters: list[SplitChapter]) -> list[dict[str, str]]:
    return [chapter.to_registry_item() for chapter in chapters]


def split_novel_text(text: str, min_chapters: int = 3) -> list[SplitChapter]:
    """Competition-facing helper: require at least 3 chapters by default."""
    return split_chapters(text=text, min_chapters=min_chapters)
