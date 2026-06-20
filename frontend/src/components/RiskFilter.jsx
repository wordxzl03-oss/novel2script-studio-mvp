import React from "react";

const FILTERS = [
  { id: "all", label: "All episodes" },
  { id: "production", label: "Production risk" },
  { id: "compliance", label: "Compliance" }
];

export default function RiskFilter({ value, counts, onChange }) {
  return (
    <div className="hazard-filter" role="group" aria-label="Episode risk filter">
      {FILTERS.map((filter) => (
        <button
          aria-pressed={value === filter.id}
          className={value === filter.id ? "active" : ""}
          key={filter.id}
          type="button"
          onClick={() => onChange(filter.id)}
        >
          <span>{filter.label}</span>
          <strong>{counts[filter.id] || 0}</strong>
        </button>
      ))}
    </div>
  );
}

