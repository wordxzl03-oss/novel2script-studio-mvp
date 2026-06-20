import React, { useEffect, useMemo, useState } from "react";

import AdaptationGraph from "../components/AdaptationGraph.jsx";
import CompressionView from "../components/CompressionView.jsx";
import LayerToggle from "../components/LayerToggle.jsx";
import ModeTabs from "../components/ModeTabs.jsx";
import ScriptView from "../components/ScriptView.jsx";
import SourceHighlight from "../components/SourceHighlight.jsx";
import SplitPane from "../components/SplitPane.jsx";
import {
  DEFAULT_LAYER_VISIBILITY,
  toggleLayer
} from "../components/layerModel.js";
import { resetPaneWidths } from "../components/splitPaneModel.js";
import { buildMainlineNodes, resolveWorkbenchSelection } from "./workbenchModel.js";
import {
  findWrittenEpisode,
  sourceTargetForBadge
} from "./provenanceModel.js";

const EMPTY_HIGHLIGHT_DATA = {
  highlight_anchors: [],
  compression_view: [],
  element_badges: []
};

export default function Workbench({ api, project, episodeNumber, onBack }) {
  const nodes = useMemo(() => buildMainlineNodes(project), [project]);
  const [mode, setMode] = useState("compare");
  const [widths, setWidths] = useState(resetPaneWidths);
  const [collapsed, setCollapsed] = useState({});
  const [sourceView, setSourceView] = useState("text");
  const [focusedRange, setFocusedRange] = useState(null);
  const [badgeNotice, setBadgeNotice] = useState("");
  const [layerVisibility, setLayerVisibility] = useState(DEFAULT_LAYER_VISIBILITY);
  const [highlightData, setHighlightData] = useState(EMPTY_HIGHLIGHT_DATA);
  const [highlightStatus, setHighlightStatus] = useState("idle");
  const [highlightError, setHighlightError] = useState("");
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
  const selectedEpisode = findWrittenEpisode(project, selection.episodeNumber);
  const selectedLabel = selectedNode
    ? `${selectedNode.label} / ${selectedNode.title}`
    : "E01 / Episode 1";

  useEffect(() => {
    let cancelled = false;
    setFocusedRange(null);
    setBadgeNotice("");
    setHighlightError("");

    if (!api || !project || !selectedEpisode) {
      setHighlightData(EMPTY_HIGHLIGHT_DATA);
      setHighlightStatus("idle");
      return () => {
        cancelled = true;
      };
    }

    setHighlightStatus("loading");
    api.getEpisodeHighlight(project, selectedEpisode.number)
      .then((data) => {
        if (cancelled) return;
        setHighlightData({ ...EMPTY_HIGHLIGHT_DATA, ...data });
        setHighlightStatus("ready");
      })
      .catch((error) => {
        if (cancelled) return;
        setHighlightData(EMPTY_HIGHLIGHT_DATA);
        setHighlightError(error?.message || "Highlight data could not be loaded.");
        setHighlightStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [api, project, selectedEpisode]);

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

  function activateBadge(badge) {
    const target = sourceTargetForBadge(badge);
    if (target) {
      setSourceView("text");
      setFocusedRange(target);
      setBadgeNotice("");
      return;
    }
    setBadgeNotice(badge?.reason || "This script element has no verified source range.");
  }

  function selectCompressionRange(target) {
    setSourceView("text");
    setFocusedRange(target);
  }

  function toggleScriptLayer(layerId) {
    setLayerVisibility((current) => toggleLayer(current, layerId));
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
      content: (
        <SourcePanel
          data={highlightData}
          error={highlightError}
          focusedRange={focusedRange}
          novel={project?.novel}
          sourceView={sourceView}
          status={highlightStatus}
          onSelectRange={selectCompressionRange}
          onViewChange={setSourceView}
        />
      )
    },
    {
      id: "script",
      label: "Script",
      kicker: "Episode draft",
      tone: "paper",
      content: (
        <ScriptPanel
          badgeNotice={badgeNotice}
          elementBadges={highlightData.element_badges}
          episode={selectedEpisode}
          layerVisibility={layerVisibility}
          registry={project?.registry}
          selectedLabel={selectedLabel}
          selectedSceneId={selection.sceneId}
          status={highlightStatus}
          onActivateBadge={activateBadge}
          onToggleLayer={toggleScriptLayer}
        />
      )
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

function SourcePanel({
  data,
  error,
  focusedRange,
  novel,
  sourceView,
  status,
  onSelectRange,
  onViewChange
}) {
  if (status === "loading") return <PanelStatus text="Loading source evidence..." />;
  if (status === "error") return <PanelStatus text={error} tone="error" />;
  if (status === "idle") return <PanelStatus text="Source evidence is available for written episodes." />;

  return (
    <div className="source-panel">
      <div className="source-view-tabs" role="tablist" aria-label="Source evidence view">
        <button
          aria-selected={sourceView === "text"}
          className={sourceView === "text" ? "active" : ""}
          role="tab"
          type="button"
          onClick={() => onViewChange("text")}
        >
          Source text
        </button>
        <button
          aria-selected={sourceView === "compression"}
          className={sourceView === "compression" ? "active" : ""}
          role="tab"
          type="button"
          onClick={() => onViewChange("compression")}
        >
          Compression basis
        </button>
      </div>
      {sourceView === "text" ? (
        <SourceHighlight
          anchors={data.highlight_anchors}
          focusedRange={focusedRange}
          novel={novel}
        />
      ) : (
        <CompressionView items={data.compression_view} onSelectRange={onSelectRange} />
      )}
    </div>
  );
}

function ScriptPanel({
  badgeNotice,
  elementBadges,
  episode,
  layerVisibility,
  registry,
  selectedLabel,
  selectedSceneId,
  status,
  onActivateBadge,
  onToggleLayer
}) {
  return (
    <div className="script-panel">
      <LayerToggle visibility={layerVisibility} onToggle={onToggleLayer} />
      {status === "loading" && <PanelStatus text="Loading script provenance..." />}
      {status === "idle" && (
        <PanelStatus text="Script provenance is available for written episodes." />
      )}
      {status === "error" && (
        <PanelStatus text="Script provenance could not be loaded." tone="error" />
      )}
      {status === "ready" && !layerVisibility.screenwriting && (
        <div className="layer-hidden-state">Screenwriting layer hidden.</div>
      )}
      {status === "ready" && layerVisibility.screenwriting && (
        <ScriptView
          badgeNotice={badgeNotice}
          elementBadges={elementBadges}
          episode={episode}
          registry={registry}
          selectedLabel={selectedLabel}
          selectedSceneId={selectedSceneId}
          onActivateBadge={onActivateBadge}
        />
      )}
    </div>
  );
}

function PanelStatus({ text, tone = "neutral" }) {
  return <div className={`provenance-status tone-${tone}`}>{text}</div>;
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
