import assert from "node:assert/strict";
import { test } from "node:test";

import {
  initialProjectState,
  projectReducer,
  stageOrder
} from "./project.js";

test("project reducer holds ProjectState and advances visible stages", () => {
  let state = projectReducer(initialProjectState, {
    type: "flow/start",
    mode: "sample-replay"
  });
  assert.equal(state.mode, "sample-replay");
  assert.equal(state.currentStage, "bootstrap");

  state = projectReducer(state, {
    type: "flow/project-loaded",
    stage: "diagnose",
    project: { project_id: "project:demo", novel: { title: "Harbor Case" } }
  });
  assert.equal(state.project.project_id, "project:demo");
  assert.equal(state.currentStage, "diagnose");
  assert.deepEqual(state.completedStages, ["bootstrap"]);

  state = projectReducer(state, {
    type: "flow/project-loaded",
    stage: "write",
    project: {
      project_id: "project:demo",
      novel: { title: "Harbor Case" },
      series: { episodes: [{ number: 1 }, { number: 2 }, { number: 3 }] }
    }
  });
  assert.equal(state.project.series.episodes.length, 3);
  assert.equal(state.currentStage, "write");
  assert.ok(stageOrder.includes("story-bible"));
});

test("project reducer records flow errors without using browser storage", () => {
  const state = projectReducer(initialProjectState, {
    type: "flow/error",
    error: "Replay recording is missing"
  });

  assert.equal(state.error, "Replay recording is missing");
  assert.equal(state.isRunning, false);
});
