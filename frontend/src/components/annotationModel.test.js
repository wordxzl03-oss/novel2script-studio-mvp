import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ANNOTATION_FLAGS,
  annotationCountLabel,
  annotationForNode,
  filterNodesByAnnotation
} from "./annotationModel.js";

test("annotation count labels use the correct singular and plural", () => {
  assert.equal(annotationCountLabel(0), "0 notes");
  assert.equal(annotationCountLabel(1), "1 note");
  assert.equal(annotationCountLabel(2), "2 notes");
});

test("annotation flags use the approved planning vocabulary", () => {
  assert.deepEqual(ANNOTATION_FLAGS, ["高潮", "起", "承", "转", "合", "待改"]);
});

test("annotations resolve by stable graph node id", () => {
  const annotations = [
    { node_id: "episode-1", flag: "高潮", note: "Protect the reveal." },
    { node_id: "scene-1-SC001", flag: "待改", note: "Shorten this scene." }
  ];

  assert.deepEqual(annotationForNode(annotations, "scene-1-SC001"), annotations[1]);
  assert.equal(annotationForNode(annotations, "episode-2"), null);
});

test("graph filters show all nodes or only nodes with the selected flag", () => {
  const nodes = [
    { id: "episode-1" },
    { id: "scene-1-SC001" },
    { id: "episode-2" }
  ];
  const annotations = [
    { node_id: "episode-1", flag: "高潮", note: "" },
    { node_id: "scene-1-SC001", flag: "待改", note: "Shorten this scene." }
  ];

  assert.equal(filterNodesByAnnotation(nodes, annotations, "all"), nodes);
  assert.deepEqual(
    filterNodesByAnnotation(nodes, annotations, "待改").map((node) => node.id),
    ["scene-1-SC001"]
  );
  assert.deepEqual(filterNodesByAnnotation(nodes, annotations, "承"), []);
});
