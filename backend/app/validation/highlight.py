from __future__ import annotations

from typing import Any, Literal

from app.rag.evidence_store import EvidenceStore
from app.rag.source_binding import resolve_episode_sources
from app.schema.short_drama import Episode, SourceLink
from app.validation.source_validation import SourceLinkVerdict, validate_source_link

BadgeState = Literal["literal_ok", "source_based", "invented", "unverified"]


def derive_badge_state(verdict: SourceLinkVerdict, link: SourceLink) -> BadgeState:
    if not verdict.resolved or verdict.verbatim_ok is False:
        return "unverified"
    if link.type == "literal_quote" and verdict.verbatim_ok is True:
        return "literal_ok"
    if link.type == "source_based":
        return "source_based"
    if link.type == "invented_for_adaptation":
        return "invented"
    return "unverified"


def compute_highlight_anchors(
    episode: Episode, store: EvidenceStore
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for source_link in episode.source_ranges:
        source_range = source_link.source_range
        if source_range is None:
            continue

        verdict = validate_source_link(source_link, store)
        anchors.append(
            {
                "chapter_id": source_range.chapter_id,
                "para_range": (source_range.start_para, source_range.end_para),
                "badge_state": derive_badge_state(verdict, source_link),
                "source_link": source_link,
            }
        )

    return anchors


def compute_element_badges(
    episode: Episode, store: EvidenceStore
) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    for scene in episode.scenes:
        for beat in scene.beats:
            for element in beat.elements:
                badges = [
                    _badge_payload(source_link, store)
                    for source_link in element.source_links
                ]
                if not badges:
                    badges = [
                        {
                            "badge_state": "unverified",
                            "source_link": None,
                            "chapter_id": None,
                            "para_range": None,
                            "reason": "No source link was provided.",
                        }
                    ]
                elements.append(
                    {
                        "scene_id": scene.scene_id,
                        "beat_id": beat.beat_id,
                        "element_id": element.element_id,
                        "badges": badges,
                    }
                )
    return elements


def compute_compression_view(
    episode: Episode, store: EvidenceStore
) -> list[dict[str, Any]]:
    view: list[dict[str, Any]] = []
    for source in resolve_episode_sources(episode, store):
        view.append(
            {
                **source,
                "text_excerpt": source["resolved_text"],
            }
        )
    return view


def _badge_payload(source_link: SourceLink, store: EvidenceStore) -> dict[str, Any]:
    verdict = validate_source_link(source_link, store)
    source_range = source_link.source_range
    reason = source_link.reason
    if reason is None and verdict.finding is not None:
        reason = verdict.finding.message
    return {
        "badge_state": derive_badge_state(verdict, source_link),
        "source_link": source_link,
        "chapter_id": source_range.chapter_id if source_range is not None else None,
        "para_range": (
            (source_range.start_para, source_range.end_para)
            if source_range is not None
            else None
        ),
        "reason": reason,
    }
