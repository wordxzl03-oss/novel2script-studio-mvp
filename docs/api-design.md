# API Design

W1 起随对外 API 填充。

## F14/F3 Highlight Preview

`GET /api/highlight-preview`

Read-only W1 endpoint for source highlight anchors and compression-view data.
Because W1 has no `ProjectStore`, the request body supplies the serialized
`episode` and `evidence_store` to evaluate:

```json
{
  "episode": { "...": "Episode JSON" },
  "evidence_store": { "chunks": [] }
}
```

Response:

```json
{
  "highlight_anchors": [
    {
      "chapter_id": "CH001",
      "para_range": [1, 1],
      "badge_state": "literal_ok",
      "source_link": {}
    }
  ],
  "compression_view": [
    {
      "source_link": {},
      "source_range": {},
      "resolved_text": "source text",
      "source_type": "source_based",
      "text_excerpt": "source text"
    }
  ],
  "element_badges": [
    {
      "scene_id": "SC001",
      "beat_id": "B001",
      "element_id": "A001",
      "badges": [
        {
          "badge_state": "literal_ok",
          "source_link": {},
          "chapter_id": "CH001",
          "para_range": [1, 1],
          "reason": null
        }
      ]
    }
  ]
}
```

This endpoint does not call an LLM, does not trigger generation, does not write
project state, and does not render F14 UI. W2+ can replace the request-body
preview shape with project/episode IDs after project storage exists.

## W2 Replay Agent Boundary

W2 does not add public HTTP endpoints for IP diagnosis or story bible
generation. The W2 path is internal and replay-testable: callers provide a
`SourceNovel`, `Registry`, and in-memory `EvidenceStore` directly to
`DiagnosisAgent` and `StoryBibleAgent`.

External API design for these agents is deferred until project storage exists,
so W2 does not introduce request/response contracts that would imply persisted
project IDs or user-facing generation state.

## W4 V1 Stateless Project API

W4 introduces the first frontend-facing V1 endpoints. The server still does not
own project storage: the frontend holds a full `ProjectState` JSON document and
posts it back for each action. Every endpoint returns the updated `ProjectState`.

`ProjectState`:

```json
{
  "project_id": "project:...",
  "novel": { "...": "SourceNovel JSON" },
  "registry": { "...": "Registry JSON" },
  "evidence_store": { "chunks": [] },
  "series": null,
  "ip_diagnosis": null,
  "story_bible": null
}
```

### `POST /api/v1/project/bootstrap`

Request:

```json
{
  "novel_text": "plain novel text",
  "title": "Harbor Case",
  "registry": { "...": "optional Registry JSON" },
  "profile_id": "female_revenge_vertical"
}
```

Behavior:

- Splits plain text into `SourceNovel` chapters with deterministic chapter IDs.
- Uses the supplied `registry`, or runs the legacy global scan when no registry
  is supplied.
- Builds an in-memory `EvidenceStore` with `chunk_novel`.
- Returns an initial `ProjectState` with serialized `evidence_store`.

### `POST /api/v1/diagnose`

Request body is top-level `ProjectState` plus optional action field
`profile_id`. The endpoint rebuilds `EvidenceStore` from
`ProjectState.evidence_store`, runs `DiagnosisAgent`, writes
`ip_diagnosis`, and returns `ProjectState`.

### `POST /api/v1/story-bible`

Request body is top-level `ProjectState` plus optional action field
`existing_bible`. The endpoint rebuilds `EvidenceStore`, runs
`StoryBibleAgent`, writes `story_bible`, indexes story-bible chunks back into
`evidence_store`, and returns `ProjectState`.

All V1 endpoints are stateless. They do not create sessions, write a database,
or depend on a `ProjectStore`. `DEMO_MODE=1` uses replay recordings and live
mode continues to use the server-side LLM configuration and rate limit.

### `POST /api/v1/plan`

Request body is top-level `ProjectState` plus optional action field
`profile_id`. The endpoint rebuilds `EvidenceStore`, ensures there is a valid
`Series` container, loads the selected short-drama profile, runs
`EpisodePlannerAgent`, writes `series.outlines`, and returns `ProjectState`.

When `ProjectState.series` is missing, the endpoint creates a deterministic
placeholder series with `series_id` `SRS001`. The placeholder episode only
keeps the V1 `Series` schema valid until the write step replaces it.

### `POST /api/v1/write`

Request body is top-level `ProjectState` plus optional action fields
`profile_id` and `max_episodes`. `max_episodes` defaults to 3 and is capped at
10. The endpoint rebuilds `EvidenceStore`, runs `EpisodeWriterAgent`, writes
`series.episodes`, then runs `RetentionPointTask` for the generated episodes and
attaches `retention_points` when validation passes.

### `POST /api/v1/episode-highlight`

Request body is top-level `ProjectState` plus `episode_number`. The endpoint is
the project-scoped convenience wrapper around `/api/highlight-preview`: it
finds the selected episode in `ProjectState.series`, rebuilds `EvidenceStore`,
and returns:

```json
{
  "highlight_anchors": [],
  "compression_view": [],
  "element_badges": []
}
```

`element_badges` contains backend-validated badge states for every script
element. Elements without source links receive an explicit `unverified` badge;
the frontend renders these states and never derives them from `source_links`.
This endpoint does not call an LLM and does not mutate project state.
