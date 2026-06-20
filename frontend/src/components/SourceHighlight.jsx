import React, { useEffect } from "react";

import { paragraphPresentation } from "../views/provenanceModel.js";

export default function SourceHighlight({ novel, anchors, focusedRange }) {
  useEffect(() => {
    if (!focusedRange) return;
    const paragraph = document.getElementById(
      paragraphId(focusedRange.chapter_id, focusedRange.para_range[0])
    );
    paragraph?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusedRange]);

  if (!novel?.chapters?.length) {
    return <div className="provenance-empty">No source novel is loaded.</div>;
  }

  return (
    <article className="source-highlight">
      {novel.chapters.map((chapter) => (
        <section className="source-chapter" key={chapter.chapter_id}>
          <header>
            <span>{chapter.chapter_id}</span>
            <h3>{chapter.title}</h3>
          </header>
          <ol>
            {chapter.paragraphs.map((paragraph, index) => {
              const paragraphNumber = index + 1;
              const presentation = paragraphPresentation(
                chapter.chapter_id,
                paragraphNumber,
                anchors,
                focusedRange
              );
              return (
                <li
                  className={paragraphClass(presentation)}
                  data-highlighted={presentation.highlighted ? "true" : "false"}
                  id={paragraphId(chapter.chapter_id, paragraphNumber)}
                  key={`${chapter.chapter_id}-${paragraphNumber}`}
                >
                  <span className="paragraph-number">{paragraphNumber}</span>
                  <p>{paragraph}</p>
                  {presentation.badgeStates.length > 0 && (
                    <span className="paragraph-source-count">
                      {presentation.badgeStates.length} source
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </article>
  );
}

function paragraphId(chapterId, paragraphNumber) {
  return `source-${chapterId}-${paragraphNumber}`;
}

function paragraphClass(presentation) {
  return [
    "source-paragraph",
    presentation.highlighted ? "highlighted" : "",
    presentation.focused ? "focused" : ""
  ].filter(Boolean).join(" ");
}
