from pathlib import Path

import pytest
import yaml

from app.linter.engine import lint_screenplay, lint_to_dicts


ROOT = Path(__file__).resolve().parents[2]


def base_screenplay() -> dict:
    return {
        "title": "测试剧本",
        "metadata": {
            "version": "0.1.0",
            "language": "zh-CN",
            "profile": "film",
        },
        "characters": [
            {
                "character_id": "C001",
                "name": "林砚",
                "aliases": [],
                "role": "protagonist",
            },
            {
                "character_id": "C002",
                "name": "周南",
                "aliases": [],
                "role": "supporting",
            },
        ],
        "locations": [
            {
                "location_id": "L001",
                "name": "巷口",
                "aliases": [],
            }
        ],
        "chapters": [
            {
                "chapter_id": "CH001",
                "title": "第1章",
                "summary": "测试章节",
            }
        ],
        "scenes": [
            {
                "scene_id": "S001",
                "title": "巷口对峙",
                "source": {
                    "chapter": "CH001",
                    "para_range": {
                        "start": 1,
                        "end": 2,
                    },
                },
                "heading": {
                    "int_ext": "EXT",
                    "location_id": "L001",
                    "time_of_day": "night",
                },
                "characters": ["C001", "C002"],
                "objective": "林砚逼问周南。",
                "conflict": "周南回避旧案。",
                "elements": [
                    {
                        "type": "action",
                        "text": "林砚把卷宗复印件递到周南面前。",
                    },
                    {
                        "type": "dialogue",
                        "speaker_id": "C001",
                        "line": "这半个名字，是你。",
                    },
                    {
                        "type": "dialogue",
                        "speaker_id": "C002",
                        "line": "你不该重新查这件事。",
                    },
                ],
                "adaptation_log": [],
            }
        ],
    }


def rule_ids(findings):
    return [finding.rule_id for finding in findings]


def test_valid_example_yaml_has_no_error_level_findings():
    data = yaml.safe_load((ROOT / "examples" / "example.yaml").read_text(encoding="utf-8"))

    findings = lint_screenplay(data)
    errors = [finding for finding in findings if finding.severity == "error"]

    assert errors == []


def test_lint_to_dicts_returns_serializable_dicts():
    findings = lint_to_dicts(base_screenplay())

    assert isinstance(findings, list)
    assert all("rule_id" in finding for finding in findings)


def test_e001_unregistered_dialogue_speaker():
    data = base_screenplay()
    data["scenes"][0]["elements"].append(
        {
            "type": "dialogue",
            "speaker_id": "C999",
            "line": "我是不存在的人。",
        }
    )

    findings = lint_screenplay(data)

    assert "E001" in rule_ids(findings)
    assert any("C999" in finding.message for finding in findings)


def test_e002_missing_and_duplicate_scene_id():
    data = base_screenplay()
    data["scenes"].append(
        {
            **base_screenplay()["scenes"][0],
            "scene_id": "S001",
        }
    )
    data["scenes"].append(
        {
            **base_screenplay()["scenes"][0],
            "scene_id": "",
        }
    )

    findings = lint_screenplay(data)

    assert rule_ids(findings).count("E002") == 2


def test_e003_dialogue_speaker_not_in_scene_characters():
    data = base_screenplay()
    data["scenes"][0]["characters"] = ["C001"]

    findings = lint_screenplay(data)

    assert "E003" in rule_ids(findings)


@pytest.mark.parametrize(
    "source",
    [
        None,
        {},
        {"chapter": "CH001"},
        {"chapter": "CH001", "para_range": {"start": 3, "end": 1}},
    ],
)
def test_e004_missing_or_invalid_source(source):
    data = base_screenplay()

    if source is None:
        data["scenes"][0].pop("source")
    else:
        data["scenes"][0]["source"] = source

    findings = lint_screenplay(data)

    assert "E004" in rule_ids(findings)


def test_e005_unregistered_heading_location():
    data = base_screenplay()
    data["scenes"][0]["heading"]["location_id"] = "L999"

    findings = lint_screenplay(data)

    assert "E005" in rule_ids(findings)


def test_e006_short_drama_requires_episode_hook():
    data = base_screenplay()
    data["metadata"]["profile"] = "short_drama"
    data["episodes"] = [
        {
            "episode_id": "EP001",
            "scene_ids": ["S001"],
            "hook": "",
            "estimated_seconds": 90,
        }
    ]

    findings = lint_screenplay(data)

    assert "E006" in rule_ids(findings)


def test_e007_short_drama_episode_duration_limit():
    data = base_screenplay()
    data["metadata"]["profile"] = "short_drama"
    data["episodes"] = [
        {
            "episode_id": "EP001",
            "scene_ids": ["S001"],
            "hook": "林砚发现新线索。",
            "estimated_seconds": 121,
        }
    ]

    findings = lint_screenplay(data)

    assert "E007" in rule_ids(findings)


def test_warnings_for_long_action_unfilmable_action_and_long_dialogue():
    data = base_screenplay()
    data["scenes"][0]["elements"] = [
        {
            "type": "action",
            "text": (
                "林砚想起三年前那个雨夜，内心感到一阵无法描述的刺痛，"
                "他觉得自己终于明白了所有问题背后的答案，但这些情绪没有任何外部动作承载。"
                "他站在原地很久，雨水顺着伞骨滴落，卷宗复印件被他反复攥紧又松开。"
            ),
        },
        {
            "type": "dialogue",
            "speaker_id": "C001",
            "line": (
                "这是一句非常非常非常非常非常非常非常非常非常非常非常非常非常长的对白，"
                "它故意超过六十个字，用来测试台词长度警告是否能够稳定触发。"
            ),
        },
    ]

    findings = lint_screenplay(data)
    ids = rule_ids(findings)

    assert "W001" in ids
    assert "W002" in ids
    assert "W003" in ids


def test_w004_ghost_character_warning():
    data = base_screenplay()
    data["scenes"].append(
        {
            **base_screenplay()["scenes"][0],
            "scene_id": "S002",
            "characters": ["C001"],
            "elements": [
                {
                    "type": "dialogue",
                    "speaker_id": "C001",
                    "line": "继续查。",
                }
            ],
        }
    )

    findings = lint_screenplay(data)

    assert "W004" in rule_ids(findings)


def test_i001_missing_objective_or_conflict():
    data = base_screenplay()
    data["scenes"][0]["objective"] = ""

    findings = lint_screenplay(data)

    assert "I001" in rule_ids(findings)