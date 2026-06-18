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
  isRunning: false,
  error: ""
};

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
        project: action.project,
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
    case "project/reset":
      return initialProjectState;
    default:
      return state;
  }
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
