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
