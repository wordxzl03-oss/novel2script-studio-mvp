from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.schema.models import Screenplay

ROOT = Path(__file__).resolve().parents[2]


def minimal_scene(scene_id: str = "S001", start: int = 1) -> dict:
    return {
        "scene_id": scene_id,
        "title": "测试场景",
        "source": {"chapter": "CH001", "para_range": {"start": start, "end": start + 1}},
        "heading": {"int_ext": "EXT", "location_id": "L001", "time_of_day": "night"},
        "characters": ["C001"],
        "elements": [{"type": "action", "text": "测试动作。"}],
    }


def base_payload() -> dict:
    return {
        "title": "测试剧本",
        "characters": [{"character_id": "C001", "name": "林砚"}],
        "locations": [{"location_id": "L001", "name": "巷口"}],
        "chapters": [{"chapter_id": "CH001", "title": "第一章", "summary": "测试章节"}],
        "scenes": [minimal_scene()],
    }


def test_example_yaml_passes_validation():
    example_path = ROOT / "examples" / "example.yaml"
    with example_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    screenplay = Screenplay.model_validate(data)

    assert screenplay.title == "雨夜来信"
    assert screenplay.metadata.profile == "short_drama"
    assert len(screenplay.chapters) == 3
    assert len(screenplay.scenes) == 3
    assert len(screenplay.episodes) == 1
    assert screenplay.episodes[0].hook is not None
    # elements 是有序异构流：S001 第二个元素应为画外音对白
    s001 = screenplay.scenes[0]
    assert s001.elements[1].type == "dialogue"
    assert s001.elements[1].mode == "vo"


def test_dialogue_speaker_must_be_in_scene_characters():
    data = base_payload()
    data["characters"].append({"character_id": "C002", "name": "周南"})
    data["scenes"][0]["elements"].append(
        {"type": "dialogue", "speaker_id": "C002", "line": "我不在本场人物表里。"}
    )
    with pytest.raises(ValidationError):
        Screenplay.model_validate(data)


def test_unregistered_speaker_is_rejected():
    data = base_payload()
    data["scenes"][0]["elements"].append(
        {"type": "dialogue", "speaker_id": "C999", "line": "我没有注册。"}
    )
    with pytest.raises(ValidationError):
        Screenplay.model_validate(data)


def test_duplicate_scene_id_is_rejected():
    data = base_payload()
    data["scenes"].append(minimal_scene(scene_id="S001", start=3))
    with pytest.raises(ValidationError):
        Screenplay.model_validate(data)


def test_short_drama_requires_episodes_with_hook():
    data = base_payload()
    data["metadata"] = {"profile": "short_drama"}

    # 没有 episodes：拒绝
    with pytest.raises(ValidationError):
        Screenplay.model_validate(data)

    # 有 episodes 但缺 hook：拒绝
    data["episodes"] = [{"number": 1, "scenes": ["S001"]}]
    with pytest.raises(ValidationError):
        Screenplay.model_validate(data)

    # 补上 hook：通过
    data["episodes"][0]["hook"] = {"type": "reveal", "description": "测试钩子"}
    Screenplay.model_validate(data)


def test_episode_referencing_unknown_scene_is_rejected():
    data = base_payload()
    data["episodes"] = [
        {
            "number": 1,
            "hook": {"type": "cliffhanger", "description": "测试钩子"},
            "scenes": ["S999"],
        }
    ]
    with pytest.raises(ValidationError):
        Screenplay.model_validate(data)


def test_unknown_extra_field_is_rejected():
    data = base_payload()
    data["scenes"][0]["made_up_field"] = "LLM 幻觉字段"
    with pytest.raises(ValidationError):
        Screenplay.model_validate(data)
