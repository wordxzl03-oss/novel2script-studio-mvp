import React from "react";

import { LAYER_OPTIONS } from "./layerModel.js";

export default function LayerToggle({ visibility, onToggle }) {
  return (
    <fieldset className="layer-toggle">
      <legend>Layers</legend>
      <div className="layer-toggle__options">
        {LAYER_OPTIONS.map((layer) => (
          <label
            className={layer.disabled ? "layer-option disabled" : "layer-option"}
            key={layer.id}
          >
            <input
              checked={layer.id === "screenwriting" && visibility.screenwriting}
              disabled={layer.disabled}
              type="checkbox"
              onChange={() => onToggle(layer.id)}
            />
            <span>{layer.label}</span>
            {layer.note && <small>{layer.note}</small>}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
