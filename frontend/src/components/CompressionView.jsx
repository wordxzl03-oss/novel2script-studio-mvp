import React from "react";

import { compressionPresentation } from "../views/provenanceModel.js";

export default function CompressionView({ items, onSelectRange }) {
  if (!items?.length) {
    return <div className="provenance-empty">No compression basis is available.</div>;
  }

  return (
    <ol className="compression-view">
      {items.map((item, index) => {
        const target = compressionTarget(item.source_range);
        return (
          <li className={`compression-item type-${item.source_type}`} key={index}>
            <header>
              <span>{compressionPresentation(item.source_type)}</span>
              {target && (
                <button type="button" onClick={() => onSelectRange(target)}>
                  {target.chapter_id}:{target.para_range[0]}-{target.para_range[1]}
                </button>
              )}
            </header>
            <p>{item.text_excerpt || item.source_link?.reason || "No source text."}</p>
          </li>
        );
      })}
    </ol>
  );
}

function compressionTarget(sourceRange) {
  if (!sourceRange?.chapter_id) return null;
  return {
    chapter_id: sourceRange.chapter_id,
    para_range: [sourceRange.start_para, sourceRange.end_para]
  };
}
