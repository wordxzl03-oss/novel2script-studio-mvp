from __future__ import annotations

from copy import deepcopy


def source_link_payload() -> dict:
    return {
        "type": "source_based",
        "source_range": {
            "chapter_id": "CH001",
            "start_para": 1,
            "end_para": 1,
        },
    }


def registry_payload() -> dict:
    return {
        "characters": [
            {"character_id": "C001", "name": "Lin Yan"},
            {"character_id": "C002", "name": "Chen Mo"},
        ],
        "locations": [
            {"location_id": "L001", "name": "Safehouse", "aliases": ["safe house"]},
        ],
        "relationship_map": [],
    }


def scene_payload(scene_id: str = "SC001", title: str = "Safehouse confrontation") -> dict:
    link = source_link_payload()
    return {
        "scene_id": scene_id,
        "title": title,
        "source_links": [link],
        "beats": [
            {
                "beat_id": f"{scene_id}-B001",
                "summary": "Lin Yan corners Chen Mo with the stolen file.",
                "elements": [
                    {
                        "element_id": f"{scene_id}-A001",
                        "type": "action",
                        "text": "Lin Yan blocks the exit with the stolen file.",
                        "source_links": [link],
                    },
                    {
                        "element_id": f"{scene_id}-D001",
                        "type": "dialogue",
                        "speaker_id": "C001",
                        "text": "You hid the truth from everyone.",
                        "source_links": [link],
                    },
                    {
                        "element_id": f"{scene_id}-A002",
                        "type": "action",
                        "text": "Chen Mo reaches for the phone on the table.",
                        "source_links": [link],
                    },
                    {
                        "element_id": f"{scene_id}-D002",
                        "type": "dialogue",
                        "speaker_id": "C002",
                        "text": "If you call them, the evidence disappears.",
                        "source_links": [link],
                    },
                ],
            }
        ],
    }


def episode_payload() -> dict:
    return {
        "episode_id": "E01",
        "number": 1,
        "title": "Letter in the Rain",
        "logline": "A sealed letter turns a cold case into a confrontation.",
        "opening_hook": "Lin Yan finds a marked letter under the door.",
        "main_conflict": "Lin Yan confronts Chen Mo over the stolen case file.",
        "emotional_payoff": "She proves she will no longer retreat.",
        "cliffhanger": "A second witness calls from the safe house.",
        "source_ranges": [source_link_payload()],
        "scenes": [scene_payload()],
    }


def outline_payload() -> dict:
    return {
        "number": 1,
        "title": "Letter in the Rain",
        "logline": "A sealed letter turns a cold case into a confrontation.",
        "opening_hook": "Lin Yan finds a marked letter under the door.",
        "main_conflict": "Lin Yan confronts Chen Mo over the stolen case file.",
        "emotional_payoff": "She proves she will no longer retreat.",
        "cliffhanger": "A second witness calls from the safe house.",
        "source_ranges": [source_link_payload()],
    }


def load_test_profile():
    from app.profiles.loader import load_profile

    return load_profile("female_revenge_vertical")


def validate_episode(payload: dict | None = None):
    from app.schema.short_drama import Episode

    return Episode.model_validate(payload or episode_payload())


def validate_outline(payload: dict | None = None):
    from app.schema.short_drama import EpisodeOutline

    return EpisodeOutline.model_validate(payload or outline_payload())


def validate_registry():
    from app.schema.short_drama import Registry

    return Registry.model_validate(registry_payload())


def finding_codes(findings) -> set[str]:
    return {finding.code for finding in findings}


def test_clean_episode_has_no_errors():
    from app.validation.short_drama_linter import lint_episode

    findings = lint_episode(
        validate_episode(),
        registry=validate_registry(),
        profile=load_test_profile(),
    )

    assert findings == []


def test_unregistered_speaker_flagged():
    from app.validation.short_drama_linter import lint_episode

    payload = episode_payload()
    payload["scenes"][0]["beats"][0]["elements"][1]["speaker_id"] = "C999"

    findings = lint_episode(
        validate_episode(payload),
        registry=validate_registry(),
        profile=load_test_profile(),
    )

    assert findings[0].code == "unregistered_character"
    assert findings[0].severity == "error"
    assert findings[0].path == "scenes[0].beats[0].elements[1].speaker_id"


def test_scene_count_out_of_range_warns():
    from app.validation.short_drama_linter import lint_episode

    payload = episode_payload()
    payload["scenes"] = [
        scene_payload(f"SC00{index}", "Safehouse confrontation")
        for index in range(1, 6)
    ]

    findings = lint_episode(
        validate_episode(payload),
        registry=validate_registry(),
        profile=load_test_profile(),
    )

    assert "scene_count_out_of_range" in finding_codes(findings)
    scene_count = next(
        finding for finding in findings if finding.code == "scene_count_out_of_range"
    )
    assert scene_count.severity == "warning"
    assert scene_count.path == "scenes"


def test_duration_out_of_range_warns():
    from app.validation.short_drama_linter import lint_episode

    profile = load_test_profile().model_copy(update={"episode_duration_sec": (1, 30)})

    findings = lint_episode(
        validate_episode(),
        registry=validate_registry(),
        profile=profile,
    )

    duration = next(
        finding for finding in findings if finding.code == "episode_duration_out_of_range"
    )
    assert duration.severity == "warning"
    assert duration.path == "scenes"


def test_placeholder_hook_flagged():
    from app.validation.short_drama_linter import lint_episode

    payload = episode_payload()
    payload["opening_hook"] = "TBD"
    payload["cliffhanger"] = "..."

    findings = lint_episode(
        validate_episode(payload),
        registry=validate_registry(),
        profile=load_test_profile(),
    )

    assert {
        "missing_opening_hook",
        "missing_cliffhanger",
    }.issubset(finding_codes(findings))
    hook = next(finding for finding in findings if finding.code == "missing_opening_hook")
    cliffhanger = next(
        finding for finding in findings if finding.code == "missing_cliffhanger"
    )
    assert hook.severity == "error"
    assert hook.path == "opening_hook"
    assert cliffhanger.severity == "error"
    assert cliffhanger.path == "cliffhanger"


def test_outline_linting_core_fields():
    from app.validation.short_drama_linter import lint_outline

    payload = outline_payload()
    payload["opening_hook"] = "?"
    payload["main_conflict"] = "conflict"

    findings = lint_outline(
        validate_outline(payload),
        registry=validate_registry(),
        profile=load_test_profile(),
    )

    assert "missing_opening_hook" in finding_codes(findings)
    assert "unclear_main_conflict" in finding_codes(findings)
    hook = next(finding for finding in findings if finding.code == "missing_opening_hook")
    conflict = next(
        finding for finding in findings if finding.code == "unclear_main_conflict"
    )
    assert hook.path == "opening_hook"
    assert conflict.path == "main_conflict"
    assert conflict.severity == "warning"


def test_unregistered_location_flagged():
    from app.validation.short_drama_linter import lint_episode

    payload = episode_payload()
    payload["scenes"][0]["title"] = "Unknown warehouse"

    findings = lint_episode(
        validate_episode(payload),
        registry=validate_registry(),
        profile=load_test_profile(),
    )

    location = next(
        finding for finding in findings if finding.code == "unregistered_location"
    )
    assert location.severity == "warning"
    assert location.path == "scenes[0].title"


def test_nested_action_and_dialogue_block_rules_use_v1_paths():
    from app.validation.short_drama_linter import lint_episode

    payload = episode_payload()
    payload["scenes"][0]["beats"][0]["elements"][0][
        "text"
    ] = "She thinks about revenge in her heart and secretly remembers every insult."
    payload["scenes"][0]["beats"][0]["elements"][1]["text"] = "A" * 180

    findings = lint_episode(
        validate_episode(payload),
        registry=validate_registry(),
        profile=load_test_profile(),
    )

    assert "unfilmable_inner_monologue" in finding_codes(findings)
    assert "block_too_long" in finding_codes(findings)
    inner = next(
        finding for finding in findings if finding.code == "unfilmable_inner_monologue"
    )
    block = next(finding for finding in findings if finding.code == "block_too_long")
    assert inner.path == "scenes[0].beats[0].elements[0].text"
    assert block.path == "scenes[0].beats[0].elements[1].text"


def test_linter_does_not_require_legacy_scene_ids():
    from app.validation.short_drama_linter import lint_episode

    payload = deepcopy(episode_payload())
    episode = validate_episode(payload)

    assert not hasattr(episode, "scene_ids")
    assert lint_episode(
        episode,
        registry=validate_registry(),
        profile=load_test_profile(),
    ) == []
