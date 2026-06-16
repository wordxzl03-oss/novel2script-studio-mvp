from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceLinkType = Literal["literal_quote", "source_based", "invented_for_adaptation"]
ElementType = Literal["action", "dialogue", "performance", "sound", "transition", "title_card"]
RetentionPointKind = Literal["hook", "reveal", "reversal", "paywall", "cliffhanger"]


class StrictModel(BaseModel):
    """Base model for V1 short-drama schema objects."""

    model_config = ConfigDict(extra="forbid")


class SourceRange(StrictModel):
    chapter_id: str = Field(min_length=1)
    start_para: int = Field(ge=1)
    end_para: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_range(self) -> "SourceRange":
        if self.end_para < self.start_para:
            raise ValueError("end_para must be greater than or equal to start_para")
        return self


class SourceLink(StrictModel):
    type: SourceLinkType
    source_range: SourceRange | None = None
    quote: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_source_link(self) -> "SourceLink":
        if self.type in {"literal_quote", "source_based"} and self.source_range is None:
            raise ValueError(f"{self.type} requires source_range")
        if self.type == "literal_quote" and not self.quote:
            raise ValueError("literal_quote requires quote")
        if self.type == "invented_for_adaptation" and not self.reason:
            raise ValueError("invented_for_adaptation requires reason")
        return self


class EvidenceMeta(StrictModel):
    source_basis: list[SourceLink] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    is_inferred: bool
    user_locked: bool = False


class EvidenceText(StrictModel):
    text: str = Field(min_length=1)
    evidence: EvidenceMeta | None = None


class ScoredItem(StrictModel):
    score: float = Field(ge=0, le=1)
    rationale: EvidenceText


class IPDiagnosis(StrictModel):
    adaptation_type: EvidenceText
    core_conflict_strength: ScoredItem
    protagonist_desire_clarity: ScoredItem
    oppression_structure: ScoredItem
    reversal_potential: ScoredItem
    vertical_fit: ScoredItem
    production_cost_risk: ScoredItem
    compliance_risk_notes: list[EvidenceText] = Field(default_factory=list)
    recommended_profile_id: str = Field(min_length=1)


class SourceChapter(StrictModel):
    chapter_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    paragraphs: list[str] = Field(min_length=1)


class SourceNovel(StrictModel):
    novel_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    author: str | None = None
    chapters: list[SourceChapter] = Field(min_length=1)


class RegistryCharacter(StrictModel):
    character_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    evidence: EvidenceMeta | None = None


class RegistryLocation(StrictModel):
    location_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    evidence: EvidenceMeta | None = None


class Relationship(StrictModel):
    from_character_id: str = Field(min_length=1)
    to_character_id: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    evidence: EvidenceMeta | None = None


class Registry(StrictModel):
    characters: list[RegistryCharacter] = Field(default_factory=list)
    locations: list[RegistryLocation] = Field(default_factory=list)
    relationship_map: list[Relationship] = Field(default_factory=list)


class StoryBible(StrictModel):
    premise: EvidenceText | None = None
    core_hook: EvidenceText | None = None
    themes: list[EvidenceText] = Field(default_factory=list)
    character_arcs: list[EvidenceText] = Field(default_factory=list)
    major_reveals: list[EvidenceText] = Field(default_factory=list)


class EpisodeOutline(StrictModel):
    number: int = Field(ge=1)
    title: str | None = None
    logline: str | None = None
    opening_hook: str = Field(min_length=1)
    main_conflict: str = Field(min_length=1)
    emotional_payoff: str = Field(min_length=1)
    cliffhanger: str = Field(min_length=1)
    source_ranges: list[SourceLink] = Field(min_length=1)


class EpisodeOutlinePlan(StrictModel):
    outlines: list[EpisodeOutline] = Field(min_length=1)


class RetentionPoint(StrictModel):
    point_id: str = Field(min_length=1)
    kind: RetentionPointKind
    description: str = Field(min_length=1)
    evidence: EvidenceMeta | None = None


class RetentionPlan(StrictModel):
    points: list[RetentionPoint] = Field(min_length=1)


class Fidelity(StrictModel):
    plot: float = Field(ge=0, le=1)
    character: float = Field(ge=0, le=1)
    theme: float = Field(ge=0, le=1)
    timeline: float = Field(ge=0, le=1)
    evidence: EvidenceMeta | None = None


class VisualLayer(StrictModel):
    vertical_focus: str | None = None
    composition_notes: list[str] = Field(default_factory=list)
    emotional_closeups: list[str] = Field(default_factory=list)
    key_props: list[str] = Field(default_factory=list)
    production_notes: list[str] = Field(default_factory=list)


class AdaptationLogEntry(StrictModel):
    log_id: str | None = None
    actor: str | None = None
    change_type: str = Field(min_length=1)
    target_ref: str | None = None
    before: str | None = None
    after: str | None = None
    reason: str = Field(min_length=1)
    created_at: str | None = None


class ActionElement(StrictModel):
    element_id: str = Field(min_length=1)
    type: Literal["action"] = "action"
    text: str = Field(min_length=1)
    source_links: list[SourceLink] = Field(default_factory=list)
    evidence: EvidenceMeta | None = None


class DialogueElement(StrictModel):
    element_id: str = Field(min_length=1)
    type: Literal["dialogue"] = "dialogue"
    speaker_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    performance_hint: str | None = None
    source_links: list[SourceLink] = Field(default_factory=list)
    evidence: EvidenceMeta | None = None


class PerformanceElement(StrictModel):
    element_id: str = Field(min_length=1)
    type: Literal["performance"] = "performance"
    text: str = Field(min_length=1)
    source_links: list[SourceLink] = Field(default_factory=list)
    evidence: EvidenceMeta | None = None


class SoundElement(StrictModel):
    element_id: str = Field(min_length=1)
    type: Literal["sound"] = "sound"
    text: str = Field(min_length=1)
    source_links: list[SourceLink] = Field(default_factory=list)
    evidence: EvidenceMeta | None = None


class TransitionElement(StrictModel):
    element_id: str = Field(min_length=1)
    type: Literal["transition"] = "transition"
    text: str = Field(min_length=1)
    source_links: list[SourceLink] = Field(default_factory=list)
    evidence: EvidenceMeta | None = None


class TitleCardElement(StrictModel):
    element_id: str = Field(min_length=1)
    type: Literal["title_card"] = "title_card"
    text: str = Field(min_length=1)
    source_links: list[SourceLink] = Field(default_factory=list)
    evidence: EvidenceMeta | None = None


Element = Annotated[
    Union[
        ActionElement,
        DialogueElement,
        PerformanceElement,
        SoundElement,
        TransitionElement,
        TitleCardElement,
    ],
    Field(discriminator="type"),
]


class Beat(StrictModel):
    beat_id: str = Field(min_length=1)
    summary: str | None = None
    elements: list[Element] = Field(min_length=1)


class Scene(StrictModel):
    scene_id: str = Field(min_length=1)
    title: str | None = None
    source_links: list[SourceLink] = Field(default_factory=list)
    beats: list[Beat] = Field(min_length=1)
    visual_layer: VisualLayer | None = None


class Episode(StrictModel):
    episode_id: str = Field(min_length=1)
    number: int = Field(ge=1)
    title: str | None = None
    logline: str | None = None
    opening_hook: str = Field(min_length=1)
    main_conflict: str = Field(min_length=1)
    emotional_payoff: str = Field(min_length=1)
    cliffhanger: str = Field(min_length=1)
    source_ranges: list[SourceLink] = Field(min_length=1)
    retention_points: list[RetentionPoint] = Field(default_factory=list)
    fidelity: Fidelity | None = None
    quality_checks: dict[str, bool | str | int | float | None] = Field(default_factory=dict)
    visual_layer: VisualLayer | None = None
    forks: list[dict[str, str]] = Field(default_factory=list)
    adaptation_log: list[AdaptationLogEntry] = Field(default_factory=list)
    scenes: list[Scene] = Field(min_length=1)


class Series(StrictModel):
    series_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    episodes: list[Episode] = Field(min_length=1)
    outlines: list[EpisodeOutline] = Field(default_factory=list)


class ShortDramaProfile(StrictModel):
    profile_id: str = Field(min_length=1)
    display_name: str | None = None
    version: str | None = None


class ShortDramaProject(StrictModel):
    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: str = Field(default="1.0.0")
    source_novel: SourceNovel
    registry: Registry = Field(default_factory=Registry)
    story_bible: StoryBible = Field(default_factory=StoryBible)
    ip_diagnosis: IPDiagnosis | None = None
    series: Series
    profile: ShortDramaProfile | None = None
