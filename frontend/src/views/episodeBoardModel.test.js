import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildEpisodeCards,
  filterEpisodeCards,
  summarizeProjectRisks
} from "./episodeBoardModel.js";

test("episode board builds ten cards and merges drafts over outlines", () => {
  const cards = buildEpisodeCards(projectFixture());

  assert.equal(cards.length, 10);
  assert.equal(cards[0].number, 1);
  assert.equal(cards[0].status, "drafted");
  assert.equal(cards[0].title, "Episode one draft");
  assert.equal(cards[0].sourceCounts.source_based, 1);
  assert.equal(cards[1].forkCount, 1);
  assert.equal(cards[3].status, "planned");
  assert.equal(cards[9].status, "pending");
});

test("risk filters use diagnosis evidence ranges instead of invented episode risk", () => {
  const project = projectFixture();
  const cards = buildEpisodeCards(project);

  assert.deepEqual(
    filterEpisodeCards(cards, "production").map((card) => card.number),
    [1]
  );
  assert.deepEqual(
    filterEpisodeCards(cards, "compliance").map((card) => card.number),
    [2]
  );
  assert.equal(filterEpisodeCards(cards, "all").length, 10);

  assert.deepEqual(summarizeProjectRisks(project, cards), {
    productionScore: 0.82,
    complianceCount: 1,
    affectedEpisodeCount: 2
  });
});

test("planner placeholder E000 is not counted as a drafted episode", () => {
  const project = projectFixture();
  project.series.episodes = [
    {
      ...project.series.outlines[0],
      episode_id: "E000",
      title: "Placeholder",
      forks: [],
      scenes: [{ scene_id: "SC000" }]
    }
  ];

  const firstCard = buildEpisodeCards(project)[0];

  assert.equal(firstCard.status, "planned");
  assert.equal(firstCard.title, "Episode 1 outline");
});

function projectFixture() {
  const outlines = Array.from({ length: 4 }, (_, index) => ({
    number: index + 1,
    title: `Episode ${index + 1} outline`,
    logline: `Logline ${index + 1}`,
    opening_hook: `Opening hook ${index + 1}`,
    main_conflict: `Main conflict ${index + 1}`,
    emotional_payoff: `Emotional payoff ${index + 1}`,
    cliffhanger: `Cliffhanger ${index + 1}`,
    source_ranges: [sourceLink(index + 1)]
  }));
  const episodes = [1, 2, 3].map((number) => ({
    ...outlines[number - 1],
    episode_id: `E${String(number).padStart(3, "0")}`,
    title: number === 1 ? "Episode one draft" : outlines[number - 1].title,
    forks: number === 2 ? [{ fork_id: "fork-1" }] : [],
    scenes: [{ scene_id: `SC${number}` }]
  }));

  return {
    project_id: "project:board-test",
    novel: { title: "Harbor Case" },
    series: {
      series_id: "SRS001",
      title: "Harbor Case",
      outlines,
      episodes
    },
    ip_diagnosis: {
      production_cost_risk: {
        score: 0.82,
        rationale: evidenceText("Archive night shoot", 1)
      },
      compliance_risk_notes: [evidenceText("Confession needs review", 2)]
    }
  };
}

function evidenceText(text, paragraph) {
  return {
    text,
    evidence: {
      source_basis: [sourceLink(paragraph)],
      confidence: 0.9,
      is_inferred: false,
      user_locked: false
    }
  };
}

function sourceLink(paragraph) {
  return {
    type: "source_based",
    source_range: {
      chapter_id: "CH001",
      start_para: paragraph,
      end_para: paragraph
    }
  };
}
