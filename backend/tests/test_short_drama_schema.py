import pytest
from pydantic import ValidationError


def minimal_project_payload() -> dict:
    return {
        "project_id": "P001",
        "title": "雨夜旧案",
        "version": "1.0.0",
        "profile": {"profile_id": "female_revenge_vertical", "display_name": "女频逆袭"},
        "source_novel": {
            "novel_id": "N001",
            "title": "雨夜旧案",
            "chapters": [
                {
                    "chapter_id": "CH001",
                    "title": "雨夜来信",
                    "paragraphs": ["雨落下来。", "她收到一封信。"],
                }
            ],
        },
        "registry": {
            "characters": [{"character_id": "C001", "name": "林砚"}],
            "locations": [{"location_id": "L001", "name": "巷口"}],
            "relationship_map": [],
        },
        "story_bible": {
            "premise": {
                "text": "一封匿名信让旧案重启。",
                "evidence": {
                    "source_basis": [
                        {
                            "type": "source_based",
                            "source_range": {"chapter_id": "CH001", "start_para": 1, "end_para": 2},
                        }
                    ],
                    "confidence": 0.8,
                    "is_inferred": False,
                    "user_locked": False,
                },
            }
        },
        "series": {
            "series_id": "SRS001",
            "title": "雨夜旧案",
            "episodes": [
                {
                    "episode_id": "E01",
                    "number": 1,
                    "title": "雨夜来信",
                    "logline": "匿名信打破平静。",
                    "opening_hook": "门缝里出现无名信。",
                    "main_conflict": "她要不要重查旧案。",
                    "emotional_payoff": "她决定不再退让。",
                    "cliffhanger": "信上出现被抹掉的名字。",
                    "source_ranges": [
                        {
                            "type": "source_based",
                            "source_range": {"chapter_id": "CH001", "start_para": 1, "end_para": 2},
                        }
                    ],
                    "retention_points": [
                        {
                            "point_id": "RP001",
                            "kind": "reveal",
                            "description": "匿名信揭示旧案未完。",
                        }
                    ],
                    "fidelity": {
                        "plot": 0.8,
                        "character": 0.8,
                        "theme": 0.7,
                        "timeline": 0.9,
                    },
                    "visual_layer": {
                        "vertical_focus": "门缝信封特写",
                        "composition_notes": ["竖屏近景"],
                    },
                    "scenes": [
                        {
                            "scene_id": "SC001",
                            "title": "巷口来信",
                            "source_links": [
                                {
                                    "type": "source_based",
                                    "source_range": {
                                        "chapter_id": "CH001",
                                        "start_para": 1,
                                        "end_para": 2,
                                    },
                                }
                            ],
                            "beats": [
                                {
                                    "beat_id": "B001",
                                    "summary": "林砚发现信封。",
                                    "elements": [
                                        {
                                            "element_id": "EL001",
                                            "type": "action",
                                            "text": "林砚在雨里停下。",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }


def test_minimal_short_drama_project_passes_validation():
    from app.schema.short_drama import ShortDramaProject

    project = ShortDramaProject.model_validate(minimal_project_payload())

    assert project.project_id == "P001"
    assert project.series.episodes[0].opening_hook == "门缝里出现无名信。"
    assert project.series.episodes[0].scenes[0].beats[0].elements[0].type == "action"


def test_short_drama_rejects_extra_fields():
    from app.schema.short_drama import ShortDramaProject

    payload = minimal_project_payload()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        ShortDramaProject.model_validate(payload)


def test_episode_requires_short_drama_core_fields():
    from app.schema.short_drama import ShortDramaProject

    for field_name in (
        "source_ranges",
        "opening_hook",
        "main_conflict",
        "emotional_payoff",
        "cliffhanger",
    ):
        payload = minimal_project_payload()
        del payload["series"]["episodes"][0][field_name]

        with pytest.raises(ValidationError):
            ShortDramaProject.model_validate(payload)


def test_episode_scenes_are_nested_objects():
    from app.schema.short_drama import ShortDramaProject

    project = ShortDramaProject.model_validate(minimal_project_payload())

    assert project.series.episodes[0].scenes[0].scene_id == "SC001"
    assert not isinstance(project.series.episodes[0].scenes[0], str)


def test_source_link_literal_quote_shape():
    from app.schema.short_drama import SourceLink

    source_link = SourceLink.model_validate(
        {
            "type": "literal_quote",
            "source_range": {"chapter_id": "CH001", "start_para": 1, "end_para": 1},
            "quote": "雨落下来。",
        }
    )

    assert source_link.type == "literal_quote"
    assert source_link.quote == "雨落下来。"


def test_source_link_invented_can_have_no_source_range_but_has_reason():
    from app.schema.short_drama import EvidenceMeta, SourceLink

    source_link = SourceLink.model_validate(
        {
            "type": "invented_for_adaptation",
            "reason": "为短剧开场增强冲突。",
        }
    )
    evidence = EvidenceMeta.model_validate(
        {
            "source_basis": [],
            "confidence": 0.4,
            "is_inferred": True,
            "user_locked": False,
        }
    )

    assert source_link.source_range is None
    assert source_link.reason == "为短剧开场增强冲突。"
    assert evidence.source_basis == []
    assert evidence.is_inferred is True


def test_legacy_screenplay_schema_still_imports():
    from app.schema.models import Screenplay

    assert Screenplay.__name__ == "Screenplay"
