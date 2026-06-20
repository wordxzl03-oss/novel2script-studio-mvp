import React from "react";

import { badgePresentation, sourceTargetForBadge } from "../views/provenanceModel.js";

export default function SourceBadge({ badge, onActivate }) {
  const presentation = badgePresentation(badge?.badge_state);
  const target = sourceTargetForBadge(badge);
  const detail = target
    ? `${target.chapter_id} paragraphs ${target.para_range[0]}-${target.para_range[1]}`
    : badge?.reason || presentation.label;

  return (
    <button
      aria-label={`${presentation.label}: ${detail}`}
      className={`source-badge state-${badge?.badge_state || "unverified"}`}
      title={detail}
      type="button"
      onClick={() => onActivate(badge)}
    >
      <span aria-hidden="true">{presentation.symbol}</span>
      {presentation.label}
    </button>
  );
}
