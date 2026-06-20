import assert from "node:assert/strict";
import { test } from "node:test";

import {
  badgePresentation,
  compressionPresentation,
  flattenEpisodeElements,
  paragraphPresentation,
  sourceTargetForBadge
} from "./provenanceModel.js";

test("badge presentation maps the four backend states without inference", () => {
  assert.deepEqual(badgePresentation("literal_ok"), {
    symbol: "✓",
    label: "Direct quote"
  });
  assert.equal(badgePresentation("source_based").symbol, "≈");
  assert.equal(badgePresentation("invented").symbol, "＋");
  assert.equal(badgePresentation("unverified").symbol, "⚠");
});

test("compression labels map backend source types and preserve unknown states", () => {
  assert.equal(compressionPresentation("literal_quote"), "Direct quote");
  assert.equal(compressionPresentation("source_based"), "Adapted source");
  assert.equal(compressionPresentation("invented_for_adaptation"), "Added for adaptation");
  assert.equal(compressionPresentation("unexpected"), "Needs review");
});

test("script elements use only backend-provided badge states", () => {
  const episode = {
    scenes: [
      {
        scene_id: "SC001",
        beats: [
          {
            beat_id: "B001",
            elements: [
              {
                element_id: "A001",
                type: "action",
                text: "Mira opens the letter.",
                source_links: [{ type: "literal_quote" }]
              },
              {
                element_id: "D001",
                type: "dialogue",
                speaker_id: "C001",
                text: "This changes everything.",
                source_links: [{ type: "invented_for_adaptation" }]
              }
            ]
          }
        ]
      },
      {
        scene_id: "SC002",
        beats: [
          {
            beat_id: "B002",
            elements: [
              {
                element_id: "A001",
                type: "action",
                text: "The same local ID appears in another scene.",
                source_links: []
              }
            ]
          }
        ]
      }
    ]
  };
  const elementBadges = [
    {
      scene_id: "SC001",
      beat_id: "B001",
      element_id: "A001",
      badges: [{ badge_state: "unverified", chapter_id: "CH001", para_range: [1, 1] }]
    },
    {
      scene_id: "SC002",
      beat_id: "B002",
      element_id: "A001",
      badges: [{ badge_state: "source_based", chapter_id: "CH001", para_range: [2, 2] }]
    }
  ];

  const rows = flattenEpisodeElements(episode, elementBadges);

  assert.equal(rows.length, 3);
  assert.deepEqual(rows[0].badges, elementBadges[0].badges);
  assert.deepEqual(rows[1].badges, []);
  assert.deepEqual(rows[2].badges, elementBadges[1].badges);
});

test("source paragraphs use backend anchors and focused range", () => {
  const anchors = [
    { chapter_id: "CH001", para_range: [2, 3], badge_state: "source_based" },
    { chapter_id: "CH001", para_range: [3, 3], badge_state: "literal_ok" }
  ];

  assert.deepEqual(paragraphPresentation("CH001", 1, anchors, null), {
    highlighted: false,
    focused: false,
    badgeStates: []
  });
  assert.deepEqual(
    paragraphPresentation("CH001", 3, anchors, {
      chapter_id: "CH001",
      para_range: [3, 3]
    }),
    {
      highlighted: true,
      focused: true,
      badgeStates: ["source_based", "literal_ok"]
    }
  );
});

test("badges jump only when the backend supplied a source range", () => {
  assert.deepEqual(
    sourceTargetForBadge({ chapter_id: "CH002", para_range: [4, 6] }),
    { chapter_id: "CH002", para_range: [4, 6] }
  );
  assert.equal(sourceTargetForBadge({ badge_state: "invented", reason: "Bridge beat" }), null);
});
