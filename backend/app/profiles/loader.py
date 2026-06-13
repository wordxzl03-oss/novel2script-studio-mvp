from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ProfileLoadError(RuntimeError):
    pass


class StrictProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShortDramaProfile(StrictProfileModel):
    profile_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    episode_duration_sec: tuple[int, int]
    opening_hook_required: bool
    cliffhanger_required: bool
    dialogue_density: Literal["low", "medium", "high"]
    scene_count_per_episode: tuple[int, int]
    preferred_conflict_types: list[str] = Field(min_length=1)
    risk_rules: list[str] = Field(default_factory=list)
    style_markdown: str = Field(min_length=1)


BUILTIN_PROFILE_DIR = Path(__file__).resolve().parent / "builtin"


def list_profiles() -> list[ShortDramaProfile]:
    profiles: list[ShortDramaProfile] = []
    if not BUILTIN_PROFILE_DIR.exists():
        return profiles

    for profile_dir in sorted(path for path in BUILTIN_PROFILE_DIR.iterdir() if path.is_dir()):
        try:
            profiles.append(_load_profile_dir(profile_dir))
        except ProfileLoadError:
            raise
    return profiles


def load_profile(profile_id: str) -> ShortDramaProfile:
    profile_dir = BUILTIN_PROFILE_DIR / profile_id
    if not profile_dir.is_dir():
        raise ProfileLoadError(f"Profile not found: {profile_id}")
    return _load_profile_dir(profile_dir)


def profile_to_context(profile: ShortDramaProfile) -> dict:
    return profile.model_dump(mode="json")


def _load_profile_dir(profile_dir: Path) -> ShortDramaProfile:
    yaml_path = profile_dir / "style.yaml"
    markdown_path = profile_dir / "style.md"

    if not yaml_path.is_file():
        raise ProfileLoadError(f"Missing style.yaml for profile: {profile_dir.name}")
    if not markdown_path.is_file():
        raise ProfileLoadError(f"Missing style.md for profile: {profile_dir.name}")

    try:
        metadata = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileLoadError(f"Invalid style.yaml for profile: {profile_dir.name}") from exc

    style_markdown = markdown_path.read_text(encoding="utf-8").strip()
    payload = {**metadata, "style_markdown": style_markdown}

    try:
        profile = ShortDramaProfile.model_validate(payload)
    except ValueError as exc:
        raise ProfileLoadError(f"Invalid profile metadata: {profile_dir.name}") from exc

    if profile.profile_id != profile_dir.name:
        raise ProfileLoadError(
            f"Profile id mismatch: directory={profile_dir.name}, yaml={profile.profile_id}"
        )
    return profile
