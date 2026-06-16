from __future__ import annotations

from string import punctuation
from typing import Iterable

from app.ai.task import FindingSeverity, ValidationFinding
from app.profiles.loader import ShortDramaProfile
from app.schema.short_drama import (
    ActionElement,
    DialogueElement,
    Episode,
    EpisodeOutline,
    Registry,
)

MIN_CORE_FIELD_CHARS = 8
MIN_CONFLICT_CHARS = 12
DEFAULT_ELEMENT_DURATION_SEC = 15
DEFAULT_MAX_ACTION_CHARS = 160
DEFAULT_MAX_DIALOGUE_CHARS = 120

PLACEHOLDER_VALUES = {
    "?",
    "...",
    "n/a",
    "na",
    "none",
    "placeholder",
    "tbd",
    "todo",
}
CONFLICT_SIGNALS = {
    "against",
    "argue",
    "battle",
    "block",
    "challenge",
    "clash",
    "confront",
    "conflict",
    "fight",
    "force",
    "must",
    "refuse",
    "resist",
    "reveal",
    "steal",
    "threat",
    "versus",
}
INNER_MONOLOGUE_SIGNALS = {
    "in her heart",
    "in his heart",
    "inner monologue",
    "realizes",
    "secretly remembers",
    "thinks",
    "thoughts",
}


def lint_episode(
    episode: Episode, *, registry: Registry, profile: ShortDramaProfile
) -> list[ValidationFinding]:
    findings = _lint_core_fields(episode, profile=profile)
    findings.extend(_lint_episode_shape(episode, registry=registry, profile=profile))
    return findings


def lint_outline(
    outline: EpisodeOutline, *, registry: Registry, profile: ShortDramaProfile
) -> list[ValidationFinding]:
    return _lint_core_fields(outline, profile=profile)


def _lint_core_fields(
    item: Episode | EpisodeOutline, *, profile: ShortDramaProfile
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if profile.opening_hook_required and _is_placeholder(item.opening_hook):
        findings.append(
            _finding(
                code="missing_opening_hook",
                severity="error",
                message="opening_hook is empty or placeholder-like",
                path="opening_hook",
            )
        )
    if _is_unclear_conflict(item.main_conflict):
        findings.append(
            _finding(
                code="unclear_main_conflict",
                severity="warning",
                message="main_conflict is too short or lacks a clear conflict signal",
                path="main_conflict",
            )
        )
    if profile.cliffhanger_required and _is_placeholder(item.cliffhanger):
        findings.append(
            _finding(
                code="missing_cliffhanger",
                severity="error",
                message="cliffhanger is empty or placeholder-like",
                path="cliffhanger",
            )
        )
    return findings


def _lint_episode_shape(
    episode: Episode, *, registry: Registry, profile: ShortDramaProfile
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    scene_count = len(episode.scenes)
    min_scenes, max_scenes = profile.scene_count_per_episode
    if scene_count < min_scenes or scene_count > max_scenes:
        findings.append(
            _finding(
                code="scene_count_out_of_range",
                severity="warning",
                message=(
                    f"scene count {scene_count} is outside profile range "
                    f"{min_scenes}-{max_scenes}"
                ),
                path="scenes",
            )
        )

    estimated_duration = _estimate_duration_sec(episode)
    min_duration, max_duration = profile.episode_duration_sec
    if estimated_duration < min_duration or estimated_duration > max_duration:
        findings.append(
            _finding(
                code="episode_duration_out_of_range",
                severity="warning",
                message=(
                    f"estimated duration {estimated_duration}s is outside profile "
                    f"range {min_duration}-{max_duration}s"
                ),
                path="scenes",
            )
        )

    character_ids = {character.character_id for character in registry.characters}
    location_tokens = _registered_location_tokens(registry)
    for scene_index, scene in enumerate(episode.scenes):
        if scene.title and not _references_registered_location(
            scene.title, location_tokens
        ):
            findings.append(
                _finding(
                    code="unregistered_location",
                    severity="warning",
                    message="scene title does not reference a registered location",
                    path=f"scenes[{scene_index}].title",
                )
            )
        for beat_index, beat in enumerate(scene.beats):
            for element_index, element in enumerate(beat.elements):
                path = f"scenes[{scene_index}].beats[{beat_index}].elements[{element_index}]"
                if isinstance(element, DialogueElement):
                    findings.extend(
                        _lint_dialogue_element(
                            element,
                            character_ids=character_ids,
                            path=path,
                        )
                    )
                elif isinstance(element, ActionElement):
                    findings.extend(_lint_action_element(element, path=path))

    return findings


def _lint_dialogue_element(
    element: DialogueElement, *, character_ids: set[str], path: str
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if element.speaker_id not in character_ids:
        findings.append(
            _finding(
                code="unregistered_character",
                severity="error",
                message=f"dialogue speaker_id is not registered: {element.speaker_id}",
                path=f"{path}.speaker_id",
            )
        )
    if len(element.text.strip()) > DEFAULT_MAX_DIALOGUE_CHARS:
        findings.append(
            _finding(
                code="block_too_long",
                severity="warning",
                message="dialogue block exceeds the default length threshold",
                path=f"{path}.text",
            )
        )
    return findings


def _lint_action_element(
    element: ActionElement, *, path: str
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    text = element.text.strip()
    if _has_inner_monologue(text):
        findings.append(
            _finding(
                code="unfilmable_inner_monologue",
                severity="warning",
                message="action text appears to describe internal thought only",
                path=f"{path}.text",
            )
        )
    if len(text) > DEFAULT_MAX_ACTION_CHARS:
        findings.append(
            _finding(
                code="block_too_long",
                severity="warning",
                message="action block exceeds the default length threshold",
                path=f"{path}.text",
            )
        )
    return findings


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    normalized = stripped.lower().strip(punctuation + " ")
    if normalized in PLACEHOLDER_VALUES:
        return True
    if len(stripped) < MIN_CORE_FIELD_CHARS:
        return True
    return all(character in punctuation for character in stripped)


def _is_unclear_conflict(value: str) -> bool:
    normalized = value.strip().lower()
    if _is_placeholder(value) or len(normalized) < MIN_CONFLICT_CHARS:
        return True
    return not any(signal in normalized for signal in CONFLICT_SIGNALS)


def _estimate_duration_sec(episode: Episode) -> int:
    element_count = sum(
        len(beat.elements)
        for scene in episode.scenes
        for beat in scene.beats
    )
    return element_count * DEFAULT_ELEMENT_DURATION_SEC


def _registered_location_tokens(registry: Registry) -> set[str]:
    tokens: set[str] = set()
    for location in registry.locations:
        tokens.add(location.location_id.lower())
        tokens.add(location.name.lower())
        tokens.update(alias.lower() for alias in location.aliases)
    return {token for token in tokens if token}


def _references_registered_location(title: str, tokens: Iterable[str]) -> bool:
    normalized = title.lower()
    return any(token in normalized for token in tokens)


def _has_inner_monologue(text: str) -> bool:
    normalized = text.lower()
    return any(signal in normalized for signal in INNER_MONOLOGUE_SIGNALS)


def _finding(
    *, code: str, severity: FindingSeverity, message: str, path: str
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=severity,
        message=message,
        path=path,
    )
