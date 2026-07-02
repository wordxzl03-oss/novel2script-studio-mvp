import React, { createContext, useContext, useReducer } from "react";

export const stageOrder = ["bootstrap", "diagnose", "story-bible", "plan", "write"];

export const stageLabels = {
  idle: "Ready",
  bootstrap: "Bootstrap",
  diagnose: "IP diagnosis",
  "story-bible": "Story bible",
  plan: "Episode plan",
  write: "Episode writing",
  complete: "Complete"
};

export const initialProjectState = {
  project: null,
  profileId: "female_revenge_vertical",
  currentStage: "idle",
  completedStages: [],
  mode: "sample-replay",
  activeView: "board",
  selectedEpisodeNumber: null,
  isRunning: false,
  error: ""
};

export function shouldExpandProjectRunner(state) {
  return !state?.project || Boolean(state?.isRunning) || Boolean(state?.error);
}

const ProjectContext = createContext(null);

export function projectReducer(state, action) {
  switch (action.type) {
    case "flow/start":
      return {
        ...state,
        mode: action.mode || state.mode,
        currentStage: "bootstrap",
        completedStages: [],
        isRunning: true,
        error: ""
      };
    case "flow/stage-start":
      return {
        ...state,
        currentStage: action.stage,
        isRunning: true,
        error: ""
      };
    case "flow/project-loaded":
      return {
        ...state,
        project: mergeProjectAnnotations(action.project, state.project),
        currentStage: action.stage,
        completedStages: previousStages(action.stage),
        error: ""
      };
    case "flow/finish":
      return {
        ...state,
        currentStage: "complete",
        completedStages: stageOrder,
        isRunning: false,
        error: ""
      };
    case "flow/error":
      return {
        ...state,
        error: action.error,
        isRunning: false
      };
    case "view/open-episode":
      return {
        ...state,
        activeView: "workbench",
        selectedEpisodeNumber: action.episodeNumber
      };
    case "view/show-board":
      return {
        ...state,
        activeView: "board"
      };
    case "annotation/save":
      return {
        ...state,
        project: saveProjectAnnotation(state.project, action.annotation)
      };
    case "project/reset":
      return initialProjectState;
    default:
      return state;
  }
}

function mergeProjectAnnotations(project, currentProject) {
  const incomingAnnotations = Array.isArray(project?.annotations)
    ? project.annotations
    : null;
  const currentAnnotations =
    currentProject?.project_id === project?.project_id &&
    Array.isArray(currentProject?.annotations)
      ? currentProject.annotations
      : [];
  return {
    ...project,
    annotations: incomingAnnotations ?? currentAnnotations
  };
}

function saveProjectAnnotation(project, annotation) {
  if (!project || !annotation?.node_id) return project;
  const annotations = Array.isArray(project.annotations) ? project.annotations : [];
  const normalized = {
    node_id: annotation.node_id,
    flag: annotation.flag || "",
    note: String(annotation.note || "").trim()
  };
  const remaining = annotations.filter(
    (item) => item.node_id !== normalized.node_id
  );
  return {
    ...project,
    annotations:
      normalized.flag || normalized.note
        ? [...remaining, normalized]
        : remaining
  };
}

export function ProjectProvider({ children }) {
  const [state, dispatch] = useReducer(projectReducer, initialProjectState);
  return React.createElement(
    ProjectContext.Provider,
    { value: { state, dispatch } },
    children
  );
}

export function useProjectState() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProjectState must be used inside ProjectProvider");
  }
  return context;
}

function previousStages(stage) {
  const index = stageOrder.indexOf(stage);
  return index > 0 ? stageOrder.slice(0, index) : [];
}
