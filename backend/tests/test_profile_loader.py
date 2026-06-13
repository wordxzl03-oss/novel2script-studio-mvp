import pytest


def evidence_chunk_payload() -> dict:
    return {
        "chunk_id": "profile:fixture:1",
        "source_type": "profile",
        "source_ref": None,
        "text": "Style profile fixture evidence.",
        "metadata": {
            "character_ids": [],
            "location_ids": [],
            "event_tags": ["profile"],
        },
    }


def test_list_profiles_contains_builtin_profile():
    from app.profiles.loader import list_profiles

    profiles = list_profiles()

    assert [profile.profile_id for profile in profiles] == ["female_revenge_vertical"]


def test_load_builtin_profile_reads_yaml_and_markdown():
    from app.profiles.loader import load_profile

    profile = load_profile("female_revenge_vertical")

    assert profile.profile_id == "female_revenge_vertical"
    assert profile.display_name == "女频逆袭"
    assert profile.episode_duration_sec == (60, 180)
    assert profile.opening_hook_required is True
    assert profile.cliffhanger_required is True
    assert profile.dialogue_density == "high"
    assert profile.scene_count_per_episode == (1, 4)
    assert profile.preferred_conflict_types == [
        "humiliation",
        "reversal",
        "identity_reveal",
    ]
    assert profile.risk_rules == ["avoid_excessive_abuse"]
    assert "女频逆袭" in profile.style_markdown


def test_profile_to_context_returns_dict():
    from app.profiles.loader import load_profile, profile_to_context

    context = profile_to_context(load_profile("female_revenge_vertical"))

    assert context["profile_id"] == "female_revenge_vertical"
    assert context["display_name"] == "女频逆袭"
    assert context["episode_duration_sec"] == [60, 180]
    assert context["opening_hook_required"] is True
    assert context["style_markdown"].startswith("# 女频逆袭")


def test_retrieval_context_accepts_profile_context():
    from app.profiles.loader import load_profile, profile_to_context
    from app.rag.types import RetrievalContext

    retrieval_context = RetrievalContext.model_validate(
        {
            "task_name": "episode_outline",
            "query": "Build episode 1 outline",
            "filters": {"episode": 1},
            "evidence_chunks": [evidence_chunk_payload()],
            "locked_items": {},
            "profile_context": profile_to_context(load_profile("female_revenge_vertical")),
            "project_memory": [],
        }
    )

    assert retrieval_context.profile_context["profile_id"] == "female_revenge_vertical"
    assert retrieval_context.profile_context["dialogue_density"] == "high"


def test_missing_profile_raises_clear_error():
    from app.profiles.loader import ProfileLoadError, load_profile

    with pytest.raises(ProfileLoadError, match="missing_profile"):
        load_profile("missing_profile")
