import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildScriptDocument,
  elementPresentation,
  resolveCharacterName
} from "./scriptViewModel.js";

const registry = {
  characters: [
    { character_id: "C001", name: "Mira", aliases: [] },
    { character_id: "C002", name: "Rowan", aliases: [] }
  ]
};

test("script document preserves scene, beat, and element hierarchy with backend badges", () => {
  const episode = {
    scenes: [
      {
        scene_id: "SC001",
        title: "The archive",
        beats: [
          {
            beat_id: "B001",
            summary: "Mira finds the hidden record.",
            elements: sampleElements()
          }
        ]
      },
      {
        scene_id: "SC002",
        title: "The pier",
        beats: [
          {
            beat_id: "B002",
            summary: null,
            elements: [
              { element_id: "A001", type: "action", text: "Rowan waits by the water." }
            ]
          }
        ]
      }
    ]
  };
  const elementBadges = [
    badgeItem("SC001", "B001", "A001", "literal_ok"),
    badgeItem("SC002", "B002", "A001", "source_based")
  ];

  const document = buildScriptDocument({ episode, registry, elementBadges });

  assert.equal(document.length, 2);
  assert.equal(document[0].sceneId, "SC001");
  assert.equal(document[0].beats[0].summary, "Mira finds the hidden record.");
  assert.equal(document[0].beats[0].elements.length, 6);
  assert.equal(document[0].beats[0].elements[0].badges[0].badge_state, "literal_ok");
  assert.equal(document[1].beats[0].elements[0].badges[0].badge_state, "source_based");
});

test("script document filters to the selected scene", () => {
  const episode = {
    scenes: [
      { scene_id: "SC001", beats: [{ beat_id: "B001", elements: sampleElements() }] },
      {
        scene_id: "SC002",
        beats: [{ beat_id: "B002", elements: [sampleElements()[0]] }]
      }
    ]
  };

  const document = buildScriptDocument({
    episode,
    registry,
    elementBadges: [],
    selectedSceneId: "SC002"
  });

  assert.deepEqual(document.map((scene) => scene.sceneId), ["SC002"]);
});

test("element presentation covers all six screenplay element types", () => {
  const presentations = sampleElements().map((element) =>
    elementPresentation(element, registry)
  );

  assert.deepEqual(
    presentations.map((item) => item.kind),
    ["action", "dialogue", "performance", "sound", "transition", "title_card"]
  );
  assert.equal(presentations[1].speakerName, "Mira");
  assert.equal(presentations[1].performanceHint, "under her breath");
  assert.equal(presentations[1].text, "The record was altered.");
  assert.equal(presentations[5].label, "Title card");
});

test("unknown character ids remain visible instead of inventing a name", () => {
  assert.equal(resolveCharacterName(registry, "C999"), "C999");
});

function sampleElements() {
  return [
    { element_id: "A001", type: "action", text: "Mira opens the archive drawer." },
    {
      element_id: "D001",
      type: "dialogue",
      speaker_id: "C001",
      text: "The record was altered.",
      performance_hint: "under her breath"
    },
    { element_id: "P001", type: "performance", text: "Mira steadies her hand." },
    { element_id: "S001", type: "sound", text: "A lock clicks in the corridor." },
    { element_id: "T001", type: "transition", text: "CUT TO:" },
    { element_id: "TC001", type: "title_card", text: "THREE YEARS EARLIER" }
  ];
}

function badgeItem(sceneId, beatId, elementId, badgeState) {
  return {
    scene_id: sceneId,
    beat_id: beatId,
    element_id: elementId,
    badges: [{ badge_state: badgeState }]
  };
}
