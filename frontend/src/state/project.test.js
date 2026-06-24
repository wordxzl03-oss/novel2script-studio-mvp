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

test("project reducer opens an episode in the workbench and returns to the board", () => {
  const project = { project_id: "project:demo" };
  let state = { ...initialProjectState, project };

  state = projectReducer(state, {
    type: "view/open-episode",
    episodeNumber: 3
  });
  assert.equal(state.activeView, "workbench");
  assert.equal(state.selectedEpisodeNumber, 3);
  assert.equal(state.project, project);

  state = projectReducer(state, { type: "view/show-board" });
  assert.equal(state.activeView, "board");
  assert.equal(state.selectedEpisodeNumber, 3);
});

test("project annotations are saved, updated, and removed by node id", () => {
  let state = {
    ...initialProjectState,
    project: { project_id: "project:demo", annotations: [] }
  };

  state = projectReducer(state, {
    type: "annotation/save",
    annotation: { node_id: "episode-1", flag: "高潮", note: "Protect this turn." }
  });
  assert.deepEqual(state.project.annotations, [
    { node_id: "episode-1", flag: "高潮", note: "Protect this turn." }
  ]);

  state = projectReducer(state, {
    type: "annotation/save",
    annotation: { node_id: "episode-1", flag: "待改", note: "  Tighten setup.  " }
  });
  assert.deepEqual(state.project.annotations, [
    { node_id: "episode-1", flag: "待改", note: "Tighten setup." }
  ]);

  state = projectReducer(state, {
    type: "annotation/save",
    annotation: { node_id: "episode-1", flag: "", note: "" }
  });
  assert.deepEqual(state.project.annotations, []);
});

test("project annotations survive backend ProjectState refreshes and JSON reloads", () => {
  const annotation = { node_id: "scene-1-SC001", flag: "转", note: "Reveal here." };
  let state = {
    ...initialProjectState,
    project: { project_id: "project:demo", annotations: [annotation] }
  };

  state = projectReducer(state, {
    type: "flow/project-loaded",
    stage: "write",
    project: { project_id: "project:demo", series: { episodes: [] } }
  });
  assert.deepEqual(state.project.annotations, [annotation]);

  state = projectReducer(initialProjectState, {
    type: "flow/project-loaded",
    stage: "bootstrap",
    project: { project_id: "project:imported", annotations: [annotation] }
  });
  assert.deepEqual(state.project.annotations, [annotation]);
});
