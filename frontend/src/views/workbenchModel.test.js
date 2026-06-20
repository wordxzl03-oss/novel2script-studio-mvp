import assert from "node:assert/strict";
import { test } from "node:test";

import { buildMainlineNodes, resolveWorkbenchSelection } from "./workbenchModel.js";

test("workbench mainline contains ten episodes and real scene nodes", () => {
  const nodes = buildMainlineNodes(projectFixture());

  assert.equal(nodes.filter((node) => node.kind === "episode").length, 10);
  assert.deepEqual(
    nodes.slice(0, 4).map((node) => node.id),
    ["episode-1", "scene-1-SC001", "scene-1-SC002", "episode-2"]
  );
  assert.equal(nodes[0].title, "First draft");
  assert.equal(nodes[1].title, "Archive entrance");
  assert.equal(nodes.at(-1).id, "episode-10");
});

test("workbench selection follows a scene and falls back to the episode", () => {
  const nodes = buildMainlineNodes(projectFixture());

  assert.deepEqual(resolveWorkbenchSelection(nodes, 1, "SC002"), {
    episodeNumber: 1,
    sceneId: "SC002",
    nodeId: "scene-1-SC002"
  });
  assert.deepEqual(resolveWorkbenchSelection(nodes, 2, "missing"), {
    episodeNumber: 2,
    sceneId: null,
    nodeId: "episode-2"
  });
});

function projectFixture() {
  return {
    series: {
      outlines: [
        { number: 1, title: "First outline" },
        { number: 2, title: "Second outline" }
      ],
      episodes: [
        {
          episode_id: "E001",
          number: 1,
          title: "First draft",
          scenes: [
            { scene_id: "SC001", title: "Archive entrance" },
            { scene_id: "SC002", title: "Hidden ledger" }
          ]
        },
        {
          episode_id: "E000",
          number: 1,
          title: "Planner placeholder",
          scenes: [{ scene_id: "SC000", title: "Placeholder" }]
        }
      ]
    }
  };
}
