import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_LAYER_VISIBILITY,
  LAYER_OPTIONS,
  toggleLayer
} from "./layerModel.js";

test("only the screenwriting layer is available in W4", () => {
  assert.deepEqual(LAYER_OPTIONS, [
    { id: "screenwriting", label: "Screenwriting", disabled: false, note: null },
    { id: "audiovisual", label: "Audiovisual", disabled: true, note: "W7" },
    { id: "production", label: "Production", disabled: true, note: "W7" }
  ]);
  assert.deepEqual(DEFAULT_LAYER_VISIBILITY, { screenwriting: true });
});

test("screenwriting can be hidden without enabling future layers", () => {
  const hidden = toggleLayer(DEFAULT_LAYER_VISIBILITY, "screenwriting");

  assert.deepEqual(hidden, { screenwriting: false });
  assert.deepEqual(toggleLayer(hidden, "audiovisual"), hidden);
  assert.deepEqual(toggleLayer(hidden, "production"), hidden);
  assert.deepEqual(toggleLayer(hidden, "screenwriting"), { screenwriting: true });
});
