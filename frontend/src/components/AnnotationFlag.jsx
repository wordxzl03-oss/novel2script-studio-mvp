import React, { useEffect, useState } from "react";

import { ANNOTATION_FLAGS } from "./annotationModel.js";

export default function AnnotationFlag({ annotation, node, onSave }) {
  const [open, setOpen] = useState(false);
  const [flag, setFlag] = useState(annotation?.flag || "");
  const [note, setNote] = useState(annotation?.note || "");

  useEffect(() => {
    setFlag(annotation?.flag || "");
    setNote(annotation?.note || "");
  }, [annotation]);

  function closeEditor() {
    setFlag(annotation?.flag || "");
    setNote(annotation?.note || "");
    setOpen(false);
  }

  function save(event) {
    event.preventDefault();
    onSave({ node_id: node.id, flag, note });
    setOpen(false);
  }

  function remove() {
    onSave({ node_id: node.id, flag: "", note: "" });
    setOpen(false);
  }

  return (
    <div className={annotation ? "annotation-flag annotated" : "annotation-flag"}>
      <button
        aria-expanded={open}
        aria-label={`Edit planning annotation for ${node.label}`}
        className="annotation-flag__trigger"
        title={annotation?.note || "Add a human planning note"}
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        <span aria-hidden="true">{annotation ? "⚑" : "+"}</span>
        {annotation?.flag || "Flag"}
      </button>
      {open && (
        <form className="annotation-editor" onSubmit={save}>
          <strong>Human planning note</strong>
          <label>
            Marker
            <select value={flag} onChange={(event) => setFlag(event.target.value)}>
              <option value="">No marker</option>
              {ANNOTATION_FLAGS.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label>
            Note
            <textarea
              aria-label={`Planning note for ${node.label}`}
              rows="3"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <div className="annotation-editor__actions">
            <button type="submit">Save</button>
            <button type="button" onClick={closeEditor}>Cancel</button>
            {annotation && (
              <button className="danger" type="button" onClick={remove}>Clear</button>
            )}
          </div>
        </form>
      )}
    </div>
  );
}
