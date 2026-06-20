import React, { useEffect, useMemo, useState } from "react";

import AdaptationGraph from "../components/AdaptationGraph.jsx";
import ModeTabs from "../components/ModeTabs.jsx";
import SplitPane from "../components/SplitPane.jsx";
import { resetPaneWidths } from "../components/splitPaneModel.js";
import { buildMainlineNodes, resolveWorkbenchSelection } from "./workbenchModel.js";

export default function Workbench({ project, episodeNumber, onBack }) {
  const nodes = useMemo(() => buildMainlineNodes(project), [project]);
  const [mode, setMode] = useState("compare");
  const [widths, setWidths] = useState(resetPaneWidths);
  const [collapsed, setCollapsed] = useState({});
  const [selection, setSelection] = useState(() =>
    resolveWorkbenchSelection(nodes, episodeNumber || 1)
  );

  useEffect(() => {
    setSelection((current) =>
      resolveWorkbenchSelection(
        nodes,
        episodeNumber || current.episodeNumber || 1,
        current.sceneId
      )
    );
  }, [episodeNumber, nodes]);

  const selectedNode =
    nodes.find((node) => node.id === selection.nodeId) || nodes[0];
  const selectedLabel = selectedNode
    ? `${selectedNode.label} / ${selectedNode.title}`
    : "E01 / Episode 1";

  function togglePane(paneId) {
    setCollapsed((current) => {
      const visibleCount = 3 - Object.values(current).filter(Boolean).length;
      if (!current[paneId] && visibleCount === 1) return current;
      return { ...current, [paneId]: !current[paneId] };
    });
  }

  function selectNode(node) {
    setSelection({
      episodeNumber: node.episodeNumber,
      sceneId: node.sceneId,
      nodeId: node.id
    });
  }

  const panes = [
    {
      id: "graph",
      label: "Adaptation graph",
      kicker: "Mainline",
      tone: "dark",
      content: (
        <AdaptationGraph
          nodes={nodes}
          selectedNodeId={selection.nodeId}
          onSelect={selectNode}
        />
      )
    },
    {
      id: "source",
      label: "Source",
      kicker: "Original text",
      tone: "paper",
      content: <ContextPlaceholder type="source" selectedLabel={selectedLabel} />
    },
    {
      id: "script",
      label: "Script",
      kicker: "Episode draft",
      tone: "paper",
      content: <ContextPlaceholder type="script" selectedLabel={selectedLabel} />
    }
  ];

  return (
    <section className="workbench" aria-labelledby="workbench-title">
      <header className="workbench-header">
        <div className="workbench-titlebar">
          <button className="back-button" type="button" onClick={onBack}>
            Back to board
          </button>
          <div>
            <p className="eyebrow">Episode workbench</p>
            <h2 id="workbench-title">
              E{String(selection.episodeNumber).padStart(2, "0")} / {selectedNode?.title}
            </h2>
          </div>
        </div>
        <ModeTabs value={mode} onChange={setMode} />
      </header>

      {mode === "compare" ? (
        <SplitPane
          collapsed={collapsed}
          panes={panes}
          widths={widths}
          onReset={() => setWidths(resetPaneWidths())}
          onResize={setWidths}
          onTogglePane={togglePane}
        />
      ) : (
        <ModePlaceholder mode={mode} selectedLabel={selectedLabel} />
      )}
    </section>
  );
}

function ContextPlaceholder({ type, selectedLabel }) {
  return (
    <div className="context-placeholder">
      <span>{type === "source" ? "Source context" : "Script context"}</span>
      <strong>{selectedLabel}</strong>
      <p>{type === "source" ? "No source passage selected." : "No script block selected."}</p>
    </div>
  );
}

function ModePlaceholder({ mode, selectedLabel }) {
  const branchMode = mode === "forks";
  return (
    <div
      aria-labelledby={`workbench-tab-${mode}`}
      className="workbench-mode-placeholder"
      role="tabpanel"
    >
      <span>{branchMode ? "Branch comparison" : "Structure overview"}</span>
      <h3>{selectedLabel}</h3>
      <p>{branchMode ? "No branch comparison is open." : "No structural track is open."}</p>
    </div>
  );
}

