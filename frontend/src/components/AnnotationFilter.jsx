import React from "react";

import {
  ANNOTATION_FLAGS,
  annotationCountLabel
} from "./annotationModel.js";

export default function AnnotationFilter({ annotations, value, onChange }) {
  return (
    <div className="annotation-filter">
      <label>
        <span>Planning notes</span>
        <select
          aria-label="Filter planning annotations"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="all">All markers</option>
          {ANNOTATION_FLAGS.map((flag) => (
            <option key={flag} value={flag}>{flag}</option>
          ))}
        </select>
      </label>
      <small>{annotationCountLabel(annotations.length)}</small>
    </div>
  );
}
