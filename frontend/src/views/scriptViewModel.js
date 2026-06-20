const ELEMENT_LABELS = {
  action: "Action",
  dialogue: "Dialogue",
  performance: "Performance",
  sound: "Sound",
  transition: "Transition",
  title_card: "Title card"
};

export function buildScriptDocument({
  episode,
  registry,
  elementBadges = [],
  selectedSceneId = null
}) {
  const badgesByElement = new Map(
    elementBadges.map((item) => [elementKey(item), item.badges || []])
  );
  const scenes = (episode?.scenes || []).filter(
    (scene) => !selectedSceneId || scene.scene_id === selectedSceneId
  );

  return scenes.map((scene) => ({
    sceneId: scene.scene_id,
    title: scene.title || scene.scene_id,
    beats: (scene.beats || []).map((beat) => ({
      beatId: beat.beat_id,
      summary: beat.summary || null,
      elements: (beat.elements || []).map((element) => ({
        elementId: element.element_id,
        ...elementPresentation(element, registry),
        badges: badgesByElement.get(elementKey({
          scene_id: scene.scene_id,
          beat_id: beat.beat_id,
          element_id: element.element_id
        })) || []
      }))
    }))
  }));
}

export function elementPresentation(element, registry) {
  const dialogue = element?.type === "dialogue";
  return {
    kind: element?.type || "unknown",
    label: ELEMENT_LABELS[element?.type] || "Element",
    text: element?.text || "",
    speakerName: dialogue
      ? resolveCharacterName(registry, element.speaker_id)
      : null,
    performanceHint: dialogue ? element.performance_hint || null : null
  };
}

export function resolveCharacterName(registry, characterId) {
  return (registry?.characters || []).find(
    (character) => character.character_id === characterId
  )?.name || characterId;
}

function elementKey(item) {
  return `${item.scene_id}\u0000${item.beat_id}\u0000${item.element_id}`;
}
