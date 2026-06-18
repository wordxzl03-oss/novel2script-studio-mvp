const DEFAULT_API_BASE = getDefaultApiBase();
const PROFILE_ID = "female_revenge_vertical";

const SAMPLE_NOVEL = [
  "Mira finds a sealed letter and decides to reopen the case.",
  "Rowan hides the letter in the archive before dawn."
].join("\n");

const SAMPLE_REGISTRY = {
  characters: [
    { character_id: "C001", name: "Mira", aliases: [] },
    { character_id: "C002", name: "Rowan", aliases: [] }
  ],
  locations: [{ location_id: "L001", name: "archive", aliases: [] }],
  relationship_map: [
    {
      from_character_id: "C001",
      to_character_id: "C002",
      relationship: "Mira suspects Rowan is hiding evidence."
    }
  ]
};

export class ApiClientError extends Error {
  constructor(message, { status = 0, code = "api_error", detail = null } = {}) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export function createV1ApiClient({
  baseUrl = DEFAULT_API_BASE,
  fetchImpl = globalThis.fetch
} = {}) {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);

  async function postJson(path, payload) {
    if (typeof fetchImpl !== "function") {
      throw new ApiClientError("Fetch API is not available in this runtime.");
    }

    const response = await fetchImpl(`${normalizedBaseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    const data = await readJson(response);

    if (!response.ok) {
      throw buildApiError(response, data);
    }

    return data;
  }

  return {
    baseUrl: normalizedBaseUrl,
    bootstrapProject(payload) {
      return postJson("/api/v1/project/bootstrap", payload);
    },
    diagnoseProject(projectState, profileId = PROFILE_ID) {
      return postJson("/api/v1/diagnose", {
        ...projectState,
        profile_id: profileId
      });
    },
    buildStoryBible(projectState, existingBible = null) {
      return postJson("/api/v1/story-bible", {
        ...projectState,
        existing_bible: existingBible
      });
    },
    planEpisodes(projectState, profileId = PROFILE_ID) {
      return postJson("/api/v1/plan", {
        ...projectState,
        profile_id: profileId
      });
    },
    writeEpisodes(projectState, { profileId = PROFILE_ID, maxEpisodes = 3 } = {}) {
      return postJson("/api/v1/write", {
        ...projectState,
        profile_id: profileId,
        max_episodes: maxEpisodes
      });
    },
    getEpisodeHighlight(projectState, episodeNumber) {
      return postJson("/api/v1/episode-highlight", {
        ...projectState,
        episode_number: episodeNumber
      });
    },
    runProjectFlow
  };

  async function runProjectFlow({
    payload = sampleReplayProjectPayload(),
    profileId = payload.profile_id || PROFILE_ID,
    maxEpisodes = 3,
    onStageStart = () => {},
    onProject = () => {}
  } = {}) {
    let project = null;

    onStageStart("bootstrap");
    project = await this.bootstrapProject(payload);
    onProject("bootstrap", project);

    onStageStart("diagnose");
    project = await this.diagnoseProject(project, profileId);
    onProject("diagnose", project);

    onStageStart("story-bible");
    project = await this.buildStoryBible(project);
    onProject("story-bible", project);

    onStageStart("plan");
    project = await this.planEpisodes(project, profileId);
    onProject("plan", project);

    onStageStart("write");
    project = await this.writeEpisodes(project, { profileId, maxEpisodes });
    onProject("write", project);

    return project;
  }
}

export function sampleReplayProjectPayload() {
  return {
    novel_text: SAMPLE_NOVEL,
    title: "Harbor Case",
    registry: SAMPLE_REGISTRY,
    profile_id: PROFILE_ID
  };
}

export function customProjectPayload({ novelText, title, profileId = PROFILE_ID }) {
  return {
    novel_text: novelText,
    title: title || "Untitled Project",
    profile_id: profileId
  };
}

export function describeApiError(error) {
  if (error instanceof ApiClientError) {
    if (error.code === "rate_limit_exceeded") {
      return "The server rate limit was reached. Wait a moment before retrying.";
    }
    if (error.code === "replay_recording_missing") {
      return "Replay recording is missing for this exact sample. Use the built-in fixture text or run the server in live mode with a configured key.";
    }
    return error.message;
  }

  return error?.message || "The V1 project flow failed.";
}

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl || "").replace(/\/+$/, "");
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function buildApiError(response, data) {
  const detail = data?.detail;
  const fallbackMessage =
    response.status >= 500
      ? "Replay recording may be missing for this exact payload, or the server hit an internal error."
      : `HTTP ${response.status}`;
  const message =
    typeof detail === "string"
      ? detail
      : detail?.message || data?.message || fallbackMessage;

  return new ApiClientError(message, {
    status: response.status,
    code:
      detail?.error ||
      data?.error ||
      (response.status >= 500 ? "replay_recording_missing" : "api_error"),
    detail
  });
}

function getDefaultApiBase() {
  return import.meta.env?.VITE_API_BASE || "http://127.0.0.1:8000";
}
