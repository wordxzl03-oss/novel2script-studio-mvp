import React, { useMemo, useState } from "react";

import {
  createV1ApiClient,
  customProjectPayload,
  describeApiError,
  sampleReplayProjectPayload
} from "./api/client.js";
import {
  ProjectProvider,
  stageLabels,
  stageOrder,
  useProjectState
} from "./state/project.js";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function App() {
  return (
    <ProjectProvider>
      <WorkbenchShell />
    </ProjectProvider>
  );
}

function WorkbenchShell() {
  const api = useMemo(() => createV1ApiClient({ baseUrl: API_BASE }), []);
  const { state, dispatch } = useProjectState();
  const samplePayload = useMemo(() => sampleReplayProjectPayload(), []);
  const [mode, setMode] = useState("sample-replay");
  const [title, setTitle] = useState(samplePayload.title);
  const [profileId, setProfileId] = useState(samplePayload.profile_id);
  const [novelText, setNovelText] = useState(samplePayload.novel_text);

  const projectTitle = state.project?.novel?.title || title || "Untitled Project";
  const episodeCount = state.project?.series?.episodes?.length || 0;
  const outlineCount = state.project?.series?.outlines?.length || 0;

  async function runFlow() {
    dispatch({ type: "flow/start", mode });
    const payload =
      mode === "sample-replay"
        ? sampleReplayProjectPayload()
        : customProjectPayload({ novelText, title, profileId });

    try {
      await api.runProjectFlow({
        payload,
        profileId: payload.profile_id,
        maxEpisodes: 3,
        onStageStart: (stage) => dispatch({ type: "flow/stage-start", stage }),
        onProject: (stage, project) =>
          dispatch({ type: "flow/project-loaded", stage, project })
      });
      dispatch({ type: "flow/finish" });
    } catch (error) {
      dispatch({ type: "flow/error", error: describeApiError(error) });
    }
  }

  function useSample() {
    const payload = sampleReplayProjectPayload();
    setMode("sample-replay");
    setTitle(payload.title);
    setProfileId(payload.profile_id);
    setNovelText(payload.novel_text);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Novel2Script Studio V1</p>
          <h1>{projectTitle}</h1>
        </div>
        <div className="topbar-meta" aria-label="Project status">
          <span>Profile: {profileId}</span>
          <span>Stage: {stageLabels[state.currentStage] || state.currentStage}</span>
          <span>{state.mode === "sample-replay" ? "Sample replay" : "Custom live"}</span>
        </div>
      </header>

      <section className="workspace-grid">
        <section className="control-panel">
          <div className="panel-title">
            <p className="eyebrow">Project intake</p>
            <h2>V1 stateless flow</h2>
          </div>

          <div className="mode-switch" role="group" aria-label="Input mode">
            <button
              className={mode === "sample-replay" ? "active" : ""}
              type="button"
              onClick={useSample}
            >
              Sample replay
            </button>
            <button
              className={mode === "custom-live" ? "active" : ""}
              type="button"
              onClick={() => setMode("custom-live")}
            >
              Custom live
            </button>
          </div>

          <label>
            Project title
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>

          <label>
            Profile
            <input value={profileId} onChange={(event) => setProfileId(event.target.value)} />
          </label>

          <label>
            Novel text
            <textarea
              value={novelText}
              onChange={(event) => setNovelText(event.target.value)}
              spellCheck="false"
            />
          </label>

          <button className="run-button" type="button" onClick={runFlow} disabled={state.isRunning}>
            {state.isRunning ? "Running V1 flow..." : "Run V1 project flow"}
          </button>

          {state.error && <div className="notice error">{state.error}</div>}
          <p className="hint">
            Sample mode uses server replay recordings. Custom text requires the backend to run
            with live LLM configuration.
          </p>
        </section>

        <section className="machine-panel">
          <div className="panel-title">
            <p className="eyebrow">Machine layer</p>
            <h2>Flow console</h2>
          </div>
          <ol className="stage-list">
            {stageOrder.map((stage) => (
              <li
                className={stageClass(stage, state)}
                key={stage}
              >
                <span>{stageLabels[stage]}</span>
                <small>{stageDescription(stage)}</small>
              </li>
            ))}
          </ol>
          <div className="api-strip">API base: {api.baseUrl}</div>
        </section>
      </section>

      <section className="view-grid">
        <section className="paper-view">
          <div className="panel-title">
            <p className="eyebrow">PR-404 placeholder</p>
            <h2>Episode board foundation</h2>
          </div>
          <div className="metric-row">
            <Metric label="Outlines" value={outlineCount} />
            <Metric label="Written episodes" value={episodeCount} />
            <Metric label="Evidence chunks" value={state.project?.evidence_store?.chunks?.length || 0} />
          </div>
          <p>
            The board view will render the first ten episode cards in PR-404. This PR only
            establishes the state and layout surface it will read from.
          </p>
        </section>

        <section className="paper-view">
          <div className="panel-title">
            <p className="eyebrow">PR-405 placeholder</p>
            <h2>Three-column workbench foundation</h2>
          </div>
          <div className="placeholder-columns" aria-label="Workbench placeholder">
            <span>Adaptation graph</span>
            <span>Source paper</span>
            <span>Script paper</span>
          </div>
          <p>
            Dragging, folding, source highlights, badges, annotations, and layer toggles stay
            reserved for later W4 PRs.
          </p>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function stageClass(stage, state) {
  if (state.currentStage === stage && state.isRunning) {
    return "active";
  }
  if (state.completedStages.includes(stage)) {
    return "done";
  }
  return "";
}

function stageDescription(stage) {
  const descriptions = {
    bootstrap: "Build SourceNovel, Registry, and EvidenceStore.",
    diagnose: "Run DiagnosisAgent through the V1 endpoint.",
    "story-bible": "Build StoryBible and index bible evidence.",
    plan: "Fill series outlines.",
    write: "Write the first three episodes."
  };
  return descriptions[stage];
}

export default App;
