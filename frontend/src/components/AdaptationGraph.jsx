import React from "react";

import AnnotationFilter from "./AnnotationFilter.jsx";
import AnnotationFlag from "./AnnotationFlag.jsx";
import {
  annotationForNode,
  filterNodesByAnnotation
} from "./annotationModel.js";

export default function AdaptationGraph({
  annotations,
  annotationFilter,
  nodes,
  selectedNodeId,
  onAnnotationFilterChange,
  onSaveAnnotation,
  onSelect
}) {
  const visibleNodes = filterNodesByAnnotation(
    nodes,
    annotations,
    annotationFilter
  );

  return (
    <nav className="adaptation-graph" aria-label="Adaptation mainline">
      <AnnotationFilter
        annotations={annotations}
        value={annotationFilter}
        onChange={onAnnotationFilterChange}
      />
      <ol>
        {visibleNodes.map((node) => (
          <li className={`graph-node ${node.kind}`} key={node.id}>
            <div className="graph-node__row">
              <button
                aria-current={selectedNodeId === node.id ? "true" : undefined}
                className={
                  selectedNodeId === node.id
                    ? "graph-node__select active"
                    : "graph-node__select"
                }
                type="button"
                onClick={() => onSelect(node)}
              >
                <span className="graph-node__label">{node.label}</span>
                <span className="graph-node__title">{node.title}</span>
              </button>
              <AnnotationFlag
                annotation={annotationForNode(annotations, node.id)}
                node={node}
                onSave={onSaveAnnotation}
              />
            </div>
          </li>
        ))}
      </ol>
      {visibleNodes.length === 0 && (
        <div className="annotation-filter-empty">No nodes match this marker.</div>
      )}
    </nav>
  );
}
