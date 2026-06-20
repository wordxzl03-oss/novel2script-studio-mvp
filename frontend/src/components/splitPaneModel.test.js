import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_PANE_WIDTHS,
  resetPaneWidths,
  resizePanePair
} from "./splitPaneModel.js";

test("resizing adjacent panes preserves their total width", () => {
  const resized = resizePanePair(DEFAULT_PANE_WIDTHS, "graph", "source", 10);

  assert.deepEqual(resized, { graph: 38, source: 26, script: 36 });
});

test("resizing clamps both panes to the readable minimum", () => {
  assert.deepEqual(
    resizePanePair(DEFAULT_PANE_WIDTHS, "graph", "source", 100),
    { graph: 46, source: 18, script: 36 }
  );
  assert.deepEqual(
    resizePanePair(DEFAULT_PANE_WIDTHS, "source", "script", -100),
    { graph: 28, source: 18, script: 54 }
  );
});

test("resetting pane widths returns a fresh default value", () => {
  const reset = resetPaneWidths();

  assert.deepEqual(reset, DEFAULT_PANE_WIDTHS);
  assert.notEqual(reset, DEFAULT_PANE_WIDTHS);
});
