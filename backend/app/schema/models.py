"""Legacy screenplay schema.

V1 short-drama project models live in backend/app/schema/short_drama.py.
Do not add new V1 objects to this file.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScriptProfile = Literal["film", "series", "short_drama"]
RoleType = Literal["protagonist", "supporting", "antagonist", "minor"]
TimeOfDay = Literal["day", "night", "dawn", "dusk", "unknown"]
IntExt = Literal["INT", "EXT", "INT_EXT"]
Fidelity = Literal["faithful", "condensed", "expanded", "invented"]
AdaptationChangeType = Literal["keep", "compress", "merge", "delete", "externalize", "rewrite"]
HookType = Literal["cliffhanger", "reveal", "reversal", "threat"]


class StrictModel(BaseModel):
    """Base model: reject unexpected fields to keep the YAML contract strict."""

    model_config = ConfigDict(extra="forbid")


class Metadata(StrictModel):
    version: str = Field(default="0.1.0")
    language: str = Field(default="zh-CN")
    profile: ScriptProfile = Field(default="film")


class Character(StrictModel):
    character_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: RoleType = "minor"
    description: str | None = None


class Location(StrictModel):
    location_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None


class Chapter(StrictModel):
    chapter_id: str
    title: str
    summary: str


class ParaRange(StrictModel):
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_range(self) -> "ParaRange":
        if self.end < self.start:
            raise ValueError("source.para_range.end must be greater than or equal to start")
        return self


class SourceRef(StrictModel):
    chapter: str
    para_range: ParaRange
    fidelity: Fidelity = "faithful"
    quote: str | None = None


class Heading(StrictModel):
    int_ext: IntExt = "INT"
    location_id: str
    time_of_day: TimeOfDay = "unknown"


# --- 场景元素：有序异构列表（剧本是动作/对白交替的顺序视听流） ---


class ActionElement(StrictModel):
    type: Literal["action"] = "action"
    text: str = Field(min_length=1)


class DialogueElement(StrictModel):
    type: Literal["dialogue"] = "dialogue"
    speaker_id: str
    line: str = Field(min_length=1)
    mode: Literal["normal", "vo", "os"] = "normal"  # vo=画外音, os=画外
    emotion: str | None = None


class TransitionElement(StrictModel):
    type: Literal["transition"] = "transition"
    text: str = Field(min_length=1)  # 如 CUT TO / DISSOLVE TO / SMASH CUT


class SoundElement(StrictModel):
    type: Literal["sound"] = "sound"
    text: str = Field(min_length=1)


class TitleCardElement(StrictModel):
    type: Literal["title_card"] = "title_card"
    text: str = Field(min_length=1)


SceneElement = Annotated[
    Union[ActionElement, DialogueElement, TransitionElement, SoundElement, TitleCardElement],
    Field(discriminator="type"),
]


class AdaptationLogItem(StrictModel):
    change_type: AdaptationChangeType
    reason: str


class Scene(StrictModel):
    scene_id: str
    title: str
    source: SourceRef
    heading: Heading
    characters: list[str] = Field(min_length=1)
    objective: str | None = None  # 戏剧学标注为可选层（schema 文档 D8）
    conflict: str | None = None
    elements: list[SceneElement] = Field(min_length=1)
    adaptation_log: list[AdaptationLogItem] = Field(default_factory=list)
    estimated_seconds: int | None = Field(default=None, ge=0)  # 由代码计算，LLM 不填


class Hook(StrictModel):
    type: HookType
    description: str


class Episode(StrictModel):
    number: int = Field(ge=1)
    title: str | None = None
    target_duration_seconds: int | None = Field(default=None, ge=1)
    hook: Hook | None = None  # short_drama profile 下必填，见 Screenplay 校验
    paywall_point: bool = False
    scenes: list[str] = Field(min_length=1)


class Screenplay(StrictModel):
    title: str
    logline: str | None = None
    metadata: Metadata = Field(default_factory=Metadata)
    characters: list[Character] = Field(min_length=1)
    locations: list[Location] = Field(min_length=1)
    chapters: list[Chapter] = Field(min_length=1)
    episodes: list[Episode] = Field(default_factory=list)
    scenes: list[Scene] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "Screenplay":
        character_ids = [c.character_id for c in self.characters]
        location_ids = [l.location_id for l in self.locations]
        chapter_ids = [c.chapter_id for c in self.chapters]
        scene_ids = [s.scene_id for s in self.scenes]
        episode_numbers = [str(e.number) for e in self.episodes]

        self._assert_unique(character_ids, "character_id")
        self._assert_unique(location_ids, "location_id")
        self._assert_unique(chapter_ids, "chapter_id")
        self._assert_unique(scene_ids, "scene_id")
        self._assert_unique(episode_numbers, "episode.number")

        character_id_set = set(character_ids)
        location_id_set = set(location_ids)
        chapter_id_set = set(chapter_ids)
        scene_id_set = set(scene_ids)

        for scene in self.scenes:
            if scene.source.chapter not in chapter_id_set:
                raise ValueError(
                    f"Scene {scene.scene_id} references unknown chapter: {scene.source.chapter}"
                )

            if scene.heading.location_id not in location_id_set:
                raise ValueError(
                    f"Scene {scene.scene_id} references unknown location: "
                    f"{scene.heading.location_id}"
                )

            scene_character_ids = set(scene.characters)

            unknown_scene_characters = scene_character_ids - character_id_set
            if unknown_scene_characters:
                raise ValueError(
                    f"Scene {scene.scene_id} contains unregistered characters: "
                    f"{sorted(unknown_scene_characters)}"
                )

            for element in scene.elements:
                if not isinstance(element, DialogueElement):
                    continue
                if element.speaker_id not in character_id_set:
                    raise ValueError(
                        f"Scene {scene.scene_id} dialogue references unregistered speaker: "
                        f"{element.speaker_id}"
                    )
                if element.speaker_id not in scene_character_ids:
                    raise ValueError(
                        f"Scene {scene.scene_id} dialogue speaker is not listed in "
                        f"scene.characters: {element.speaker_id}"
                    )

        for episode in self.episodes:
            unknown_scenes = set(episode.scenes) - scene_id_set
            if unknown_scenes:
                raise ValueError(
                    f"Episode {episode.number} references unknown scenes: "
                    f"{sorted(unknown_scenes)}"
                )

        if self.metadata.profile == "short_drama":
            if not self.episodes:
                raise ValueError("short_drama profile requires at least one episode")
            for episode in self.episodes:
                if episode.hook is None:
                    raise ValueError(
                        f"short_drama profile requires a hook for episode {episode.number}"
                    )

        return self

    @staticmethod
    def _assert_unique(values: list[str], field_name: str) -> None:
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise ValueError(f"Duplicate {field_name}: {duplicates}")
