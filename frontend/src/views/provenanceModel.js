const BADGE_PRESENTATIONS = {
  literal_ok: { symbol: "✓", label: "Direct quote" },
  source_based: { symbol: "≈", label: "Based on source" },
  invented: { symbol: "＋", label: "Added for adaptation" },
  unverified: { symbol: "⚠", label: "Needs review" }
};

const COMPRESSION_PRESENTATIONS = {
  literal_quote: "Direct quote",
  source_based: "Adapted source",
  invented_for_adaptation: "Added for adaptation"
};

export function badgePresentation(state) {
  return BADGE_PRESENTATIONS[state] || BADGE_PRESENTATIONS.unverified;
}

export function compressionPresentation(sourceType) {
  return COMPRESSION_PRESENTATIONS[sourceType] || "Needs review";
}

export function flattenEpisodeElements(episode, elementBadges = []) {
  const badgesByElement = new Map(
    elementBadges.map((item) => [elementKey(item), item.badges || []])
  );

  return (episode?.scenes || []).flatMap((scene) =>
    (scene.beats || []).flatMap((beat) =>
      (beat.elements || []).map((element) => ({
        sceneId: scene.scene_id,
        sceneTitle: scene.title || scene.scene_id,
        beatId: beat.beat_id,
        element,
        badges: badgesByElement.get(elementKey({
          scene_id: scene.scene_id,
          beat_id: beat.beat_id,
          element_id: element.element_id
        })) || []
      }))
    )
  );
}

function elementKey(item) {
  return `${item.scene_id}\u0000${item.beat_id}\u0000${item.element_id}`;
}

export function paragraphPresentation(
  chapterId,
  paragraphNumber,
  anchors = [],
  focusedRange = null
) {
  const matchingAnchors = anchors.filter((anchor) =>
    rangeContains(anchor, chapterId, paragraphNumber)
  );
  return {
    highlighted: matchingAnchors.length > 0,
    focused: rangeContains(focusedRange, chapterId, paragraphNumber),
    badgeStates: matchingAnchors.map((anchor) => anchor.badge_state)
  };
}

export function sourceTargetForBadge(badge) {
  if (!badge?.chapter_id || !validRange(badge.para_range)) return null;
  return {
    chapter_id: badge.chapter_id,
    para_range: badge.para_range
  };
}

export function findWrittenEpisode(project, episodeNumber) {
  return (project?.series?.episodes || []).find(
    (episode) =>
      episode.episode_id !== "E000" && episode.number === episodeNumber
  ) || null;
}

function rangeContains(range, chapterId, paragraphNumber) {
  return Boolean(
    range?.chapter_id === chapterId &&
      validRange(range.para_range) &&
      range.para_range[0] <= paragraphNumber &&
      paragraphNumber <= range.para_range[1]
  );
}

function validRange(range) {
  return Array.isArray(range) && range.length === 2;
}
