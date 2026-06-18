import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ApiClientError,
  createV1ApiClient,
  sampleReplayProjectPayload
} from "./client.js";

test("V1 client posts to every stateless project endpoint", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      json: async () => ({ project_id: `project-${calls.length}` })
    };
  };
  const api = createV1ApiClient({
    baseUrl: "http://api.example",
    fetchImpl
  });

  const payload = sampleReplayProjectPayload();
  const bootstrapState = await api.bootstrapProject(payload);
  const diagnosedState = await api.diagnoseProject(bootstrapState, payload.profile_id);
  const bibleState = await api.buildStoryBible(diagnosedState);
  const plannedState = await api.planEpisodes(bibleState, payload.profile_id);
  const writtenState = await api.writeEpisodes(plannedState, {
    profileId: payload.profile_id,
    maxEpisodes: 3
  });
  await api.getEpisodeHighlight(writtenState, 1);

  assert.deepEqual(
    calls.map((call) => call.url),
    [
      "http://api.example/api/v1/project/bootstrap",
      "http://api.example/api/v1/diagnose",
      "http://api.example/api/v1/story-bible",
      "http://api.example/api/v1/plan",
      "http://api.example/api/v1/write",
      "http://api.example/api/v1/episode-highlight"
    ]
  );
  assert.equal(JSON.parse(calls[4].options.body).max_episodes, 3);
  assert.equal(JSON.parse(calls[5].options.body).episode_number, 1);
});

test("V1 client surfaces friendly structured errors", async () => {
  const api = createV1ApiClient({
    baseUrl: "http://api.example",
    fetchImpl: async () => ({
      ok: false,
      status: 429,
      json: async () => ({
        detail: {
          error: "rate_limit_exceeded",
          message: "Too many requests"
        }
      })
    })
  });

  await assert.rejects(
    () => api.bootstrapProject(sampleReplayProjectPayload()),
    (error) => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.status, 429);
      assert.equal(error.code, "rate_limit_exceeded");
      assert.equal(error.message, "Too many requests");
      return true;
    }
  );
});
