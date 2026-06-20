const EPISODE_COUNT = 10;

export function buildMainlineNodes(project) {
  const outlines = indexByNumber(project?.series?.outlines || []);
  const episodes = indexByNumber(
    (project?.series?.episodes || []).filter((episode) => episode.episode_id !== "E000")
  );

  return Array.from({ length: EPISODE_COUNT }, (_, index) => index + 1).flatMap(
    (episodeNumber) => {
      const episode = episodes.get(episodeNumber);
      const outline = outlines.get(episodeNumber);
      const episodeNode = {
        id: `episode-${episodeNumber}`,
        kind: "episode",
        episodeNumber,
        sceneId: null,
        label: `E${String(episodeNumber).padStart(2, "0")}`,
        title: episode?.title || outline?.title || `Episode ${episodeNumber}`
      };
      const sceneNodes = (episode?.scenes || []).map((scene, sceneIndex) => ({
        id: `scene-${episodeNumber}-${scene.scene_id}`,
        kind: "scene",
        episodeNumber,
        sceneId: scene.scene_id,
        label: scene.scene_id || `S${String(sceneIndex + 1).padStart(2, "0")}`,
        title: scene.title || `Scene ${sceneIndex + 1}`
      }));

      return [episodeNode, ...sceneNodes];
    }
  );
}

export function resolveWorkbenchSelection(nodes, episodeNumber, sceneId = null) {
  const exactScene = sceneId
    ? nodes.find(
        (node) => node.episodeNumber === episodeNumber && node.sceneId === sceneId
      )
    : null;
  const episodeNode = nodes.find(
    (node) => node.kind === "episode" && node.episodeNumber === episodeNumber
  );
  const selected = exactScene || episodeNode || nodes[0];

  return {
    episodeNumber: selected?.episodeNumber || 1,
    sceneId: selected?.sceneId || null,
    nodeId: selected?.id || "episode-1"
  };
}

function indexByNumber(items) {
  return new Map(items.map((item) => [item.number, item]));
}
