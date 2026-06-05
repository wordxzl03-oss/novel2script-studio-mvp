from pathlib import Path

import pytest
import yaml

from app.pipeline.chapter_splitter import (
    ChapterSplitError,
    build_chapter_registry,
    is_chapter_heading,
    split_chapters,
    split_novel_text,
)
from app.schema.models import Screenplay

ROOT = Path(__file__).resolve().parents[2]


def test_sample_novel_splits_into_three_chapters():
    text = (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    chapters = split_novel_text(text)

    assert len(chapters) == 3
    assert [c.chapter_id for c in chapters] == ["CH001", "CH002", "CH003"]
    assert chapters[0].title == "第1章 雨夜来信"
    assert chapters[1].title == "第2章 旧案卷宗"
    assert chapters[2].title == "第3章 巷口重逢"
    assert "信封" in chapters[0].content
    assert "卷宗" in chapters[1].content
    assert "周南" in chapters[2].content
    assert chapters[0].para_count >= 3
    assert chapters[0].start_line < chapters[0].end_line


def test_build_chapter_registry_matches_schema_shape():
    text = (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    registry = build_chapter_registry(split_novel_text(text))

    assert len(registry) == 3
    assert registry[0]["chapter_id"] == "CH001"
    assert registry[0]["title"] == "第1章 雨夜来信"
    assert registry[0]["summary"]


@pytest.mark.parametrize(
    "line",
    [
        "第1章 雨夜来信",
        "第一章 雨夜来信",
        "第一章雨夜来信",  # 网文常见：编号与标题无空格
        "第三回 巷口重逢",
        "第两百章 重逢",
        "Chapter 1: The Letter",
        "1. 雨夜来信",
        "1、雨夜来信",
        "1.雨夜来信",
    ],
)
def test_chapter_heading_patterns_are_supported(line):
    assert is_chapter_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "第一卷 风云",       # 分卷行不是章
        "第二部 归来",
        "他翻到第三章才发现，整页证词都被人撕掉了，只剩下装订线上的纸屑。",  # 长叙述句
        "",
    ],
)
def test_non_heading_lines_are_rejected(line):
    assert not is_chapter_heading(line)


def test_volume_divider_does_not_crash_split():
    text = (
        "第一卷 风云\n\n第1章 开始\n\n内容一。\n\n第2章 转折\n\n内容二。\n\n"
        "第二卷 再起\n\n第3章 结尾\n\n内容三。"
    )
    chapters = split_chapters(text, min_chapters=3)
    assert [c.title for c in chapters] == ["第1章 开始", "第2章 转折", "第3章 结尾"]
    assert "第二卷" not in chapters[1].content  # 分卷行不得混入正文


def test_one_line_per_paragraph_convention_is_supported():
    text = (
        "第1章 开端\n他推开门。\n屋里没有人。\n桌上有一封信。\n\n"
        "第2章 中段\n内容甲。\n内容乙。\n\n第3章 结尾\n内容丙。"
    )
    chapters = split_chapters(text, min_chapters=3)
    assert chapters[0].para_count == 3
    assert chapters[0].paragraphs()[1] == "屋里没有人。"


def test_arabic_numbered_chapters_are_supported():
    text = "1. 起点\n\n第一段内容。\n\n2. 转折\n\n第二段内容。\n\n3. 结尾\n\n第三段内容。"
    chapters = split_chapters(text, min_chapters=3)
    assert [c.title for c in chapters] == ["1. 起点", "2. 转折", "3. 结尾"]


def test_min_chapters_validation_rejects_too_short_text():
    text = "第1章 只有一章\n\n这里只写了一章内容。"
    with pytest.raises(ChapterSplitError):
        split_chapters(text, min_chapters=3)


def test_empty_text_is_rejected():
    with pytest.raises(ChapterSplitError):
        split_chapters("   \n\n   ", min_chapters=1)


def test_single_body_without_heading_can_be_allowed_when_min_chapters_is_one():
    text = "没有章节标题，但这是一段正文。"
    chapters = split_chapters(text, min_chapters=1)
    assert len(chapters) == 1
    assert chapters[0].chapter_id == "CH001"
    assert chapters[0].title == "正文"
    assert chapters[0].content == text


def test_example_yaml_source_ranges_fit_sample_novel():
    """守住核心承诺：示例剧本里每个场景的溯源区间，必须真实落在示例小说的段落范围内。

    这条测试把 PR2（Schema）和 PR3（切章）扣在一起：如果有人改了样例小说或剧本，
    导致 para_range 越界，CI 会立刻发现。这也是未来 Linter 规则的雏形。
    """
    text = (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    chapters = {c.chapter_id: c for c in split_novel_text(text)}

    data = yaml.safe_load((ROOT / "examples" / "example.yaml").read_text(encoding="utf-8"))
    screenplay = Screenplay.model_validate(data)

    for scene in screenplay.scenes:
        chapter = chapters[scene.source.chapter]
        assert scene.source.para_range.end <= chapter.para_count, (
            f"{scene.scene_id} 的 para_range.end={scene.source.para_range.end} "
            f"超出 {chapter.chapter_id} 的实际段落数 {chapter.para_count}"
        )
        if scene.source.quote:
            assert scene.source.quote in chapter.content, (
                f"{scene.scene_id} 的 quote 在原文中找不到（应为逐字引用）"
            )
