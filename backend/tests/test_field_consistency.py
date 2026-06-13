from pathlib import Path

from app.linter.engine import lint_screenplay
from app.schema.models import Episode as LegacyEpisode
from app.schema.short_drama import Episode as V1Episode


ROOT = Path(__file__).resolve().parents[2]


def minimal_legacy_short_drama() -> dict:
    return {
        "title": "Field consistency sample",
        "metadata": {"profile": "short_drama"},
        "characters": [
            {"character_id": "C001", "name": "Lead", "role": "protagonist"}
        ],
        "locations": [{"location_id": "L001", "name": "Room"}],
        "chapters": [{"chapter_id": "CH001", "title": "Start", "summary": "Start"}],
        "episodes": [
            {
                "number": 1,
                "hook": {"type": "reveal", "description": "A hook"},
                "scenes": ["S001"],
            }
        ],
        "scenes": [
            {
                "scene_id": "S001",
                "title": "Opening",
                "source": {
                    "chapter": "CH001",
                    "para_range": {"start": 1, "end": 1},
                    "fidelity": "faithful",
                },
                "heading": {
                    "int_ext": "INT",
                    "location_id": "L001",
                    "time_of_day": "night",
                },
                "characters": ["C001"],
                "objective": "Find the clue",
                "conflict": "The clue is hidden",
                "elements": [
                    {"type": "action", "text": "The lead searches the room carefully."},
                    {
                        "type": "dialogue",
                        "speaker_id": "C001",
                        "line": "This room hides the answer.",
                    },
                ],
            }
        ],
    }


def rule_ids(findings):
    return {finding.rule_id for finding in findings}


def test_legacy_episode_field_is_documented():
    docs = (ROOT / "docs" / "schema-design.md").read_text(encoding="utf-8")

    assert "scenes" in LegacyEpisode.model_fields
    assert "scene_ids" not in LegacyEpisode.model_fields
    assert "legacy `Episode.scenes` stores scene id strings" in docs
    assert "legacy `Episode` does not use `scene_ids`" in docs


def test_v1_episode_field_is_documented():
    docs = (ROOT / "docs" / "schema-design.md").read_text(encoding="utf-8")

    assert "scenes" in V1Episode.model_fields
    assert "scene_ids" not in V1Episode.model_fields
    assert "V1 `Episode.scenes` stores nested `Scene` objects" in docs
    assert "V1 `Episode` does not use `scene_ids`" in docs


def test_linter_reads_declared_episode_field():
    data = minimal_legacy_short_drama()

    findings = lint_screenplay(data, short_drama_episode_seconds_limit=1)

    assert "E007" in rule_ids(findings)


def test_no_silent_scene_ids_scenes_mismatch():
    data = minimal_legacy_short_drama()
    data["episodes"][0]["scene_ids"] = data["episodes"][0].pop("scenes")

    findings = lint_screenplay(data, short_drama_episode_seconds_limit=1)

    assert "E007" not in rule_ids(findings)
    assert any(
        finding.path == "episodes[0].scenes" and "scene_ids" in finding.message
        for finding in findings
    )
