import React from "react";

const MODES = [
  { id: "compare", label: "Compare" },
  { id: "forks", label: "Branch comparison" },
  { id: "overview", label: "Structure overview" }
];

export default function ModeTabs({ value, onChange }) {
  return (
    <div className="mode-tabs" role="tablist" aria-label="Workbench mode">
      {MODES.map((mode) => (
        <button
          aria-selected={value === mode.id}
          className={value === mode.id ? "active" : ""}
          id={`workbench-tab-${mode.id}`}
          key={mode.id}
          role="tab"
          type="button"
          onClick={() => onChange(mode.id)}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}

