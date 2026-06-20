import React from "react";

export default function AdaptationGraph({ nodes, selectedNodeId, onSelect }) {
  return (
    <nav className="adaptation-graph" aria-label="Adaptation mainline">
      <ol>
        {nodes.map((node) => (
          <li className={`graph-node ${node.kind}`} key={node.id}>
            <button
              aria-current={selectedNodeId === node.id ? "true" : undefined}
              className={selectedNodeId === node.id ? "active" : ""}
              type="button"
              onClick={() => onSelect(node)}
            >
              <span className="graph-node__label">{node.label}</span>
              <span className="graph-node__title">{node.title}</span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}

