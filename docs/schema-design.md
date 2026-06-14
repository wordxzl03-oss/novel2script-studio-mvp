# Schema Design

> Scope: this document defines the V1 short-drama data contract. Runtime agents,
> LLM orchestration, RAG retrieval, and API wiring are outside PR-004.

## 1. Legacy Boundary

`backend/app/schema/models.py` remains the legacy screenplay schema used by the
existing pipeline. It keeps `Screenplay`, legacy `Episode`, legacy `Scene`, and
the current `/api/generate` contract.

legacy `Episode.scenes` stores scene id strings that reference top-level
`Screenplay.scenes`. legacy `Episode` does not use `scene_ids`.

V1 short-drama objects live in `backend/app/schema/short_drama.py`.

Rules:

1. Do not delete or rewrite the legacy schema.
2. Do not add V1 domain objects to `models.py`.
3. Keep legacy tests importing `app.schema.models.Screenplay`.
4. Add new V1 schema fields to `short_drama.py` and document them here.

## 2. V1 Object Graph

The V1 project structure is nested and episode-first:

```text
ShortDramaProject
  series: Series
    episodes: list[Episode]
      scenes: list[Scene]
        beats: list[Beat]
          elements: list[Element]
```

`Episode` owns nested `Scene` objects directly. V1 does not use `scene_ids` as
the primary episode structure.

V1 `Episode.scenes` stores nested `Scene` objects. V1 `Episode` does not use `scene_ids`.

## 3. Required Core Models

PR-004 introduces the following schema objects:

- `StrictModel`
- `SourceRange`
- `SourceLink`
- `EvidenceMeta`
- `EvidenceText`
- `ScoredItem`
- `IPDiagnosis`
- `SourceNovel`
- `RegistryCharacter`
- `RegistryLocation`
- `Registry`
- `StoryBible`
- `RetentionPoint`
- `Fidelity`
- `VisualLayer`
- `AdaptationLogEntry`
- `Element`
- `Beat`
- `Scene`
- `Episode`
- `Series`
- `ShortDramaProject`

All V1 models inherit strict extra-field rejection through `StrictModel`.

## 4. Source And Evidence

`SourceRange` identifies a source novel range by:

- `chapter_id`
- `start_para`
- `end_para`

`SourceLink` describes how an output field relates to source material:

- `literal_quote`: requires `source_range` and `quote`
- `source_based`: requires `source_range`
- `invented_for_adaptation`: requires `reason`, and may omit `source_range` and
  `quote`

`EvidenceMeta` owns evidence state:

- `source_basis: list[SourceLink]`
- `confidence`
- `is_inferred`
- `user_locked`

`source_basis` belongs to `EvidenceMeta`, not to `SourceLink`.
For `invented_for_adaptation`, `EvidenceMeta.source_basis` may be empty and
`EvidenceMeta.is_inferred` may be `true`.

### Evidence Chunks

`chunk_novel` turns `SourceNovel.chapters[].paragraphs` into paragraph-level
`EvidenceChunk` objects with `source_type="novel"`.

Chunk rules:

- `chunk_id` is deterministic: `{chapter_id}:p{start}-{end}`.
- Paragraph ranges are 1-based and stored as `EvidenceMetadata.para_range`.
- `source_ref` points back to the chunk range with a `source_based` `SourceLink`.
- `source_hash` hashes normalized chunk text. Normalization trims only leading
  and trailing whitespace, including full-width spaces and line breaks. It does
  not remove punctuation, fold case, or collapse internal whitespace.
- `character_ids` and `location_ids` are filled by deterministic string matches
  against registry names and aliases.
- LLM-dependent fields stay empty in W1: `event_tags=[]`, `conflict_type=None`,
  and `emotional_tone=None`.

### Evidence Store And Indexes

`EvidenceStore` is a standalone in-memory object for W1 evidence queries. It is
not part of `ShortDramaProject` state and is not attached to a backend
`ProjectStore`.

Store rules:

- `add_chunks` accepts `EvidenceChunk` objects and indexes them by `chunk_id`.
- `get` returns an exact chunk id match or `None`.
- `get_by_range(chapter_id, para_range)` only returns novel chunks whose
  paragraph ranges overlap the requested inclusive range.
- Range results are sorted deterministically by `chapter_id`, paragraph start,
  paragraph end, and `chunk_id`.
- `list_by_tag` supports character, location, and event tag filters through
  deterministic inverted indexes.
- `to_json` persists only chunks. `from_json` validates chunks and rebuilds
  indexes from those chunks.

W1 does not introduce a database, ORM, vector store, embedding index,
`RetrievalContext` assembly, or LLM-driven evidence tagging.

### Source Validation

`backend/app/validation/source_validation.py` validates individual `SourceLink`
objects without mutating them. It returns a `SourceLinkVerdict`; later pipeline
steps decide whether to apply suggested changes or write adaptation logs.

Validation rules:

- `literal_quote` resolves `SourceLink.source_range` through `EvidenceStore`,
  requires complete paragraph coverage, and checks whether the normalized quote
  is an exact contiguous substring of the normalized source text.
- Normalization reuses `chunk_novel` behavior: trim only leading and trailing
  whitespace; do not fold case, remove punctuation, collapse internal
  whitespace, or apply fuzzy matching.
- A literal quote mismatch produces an error finding and suggests
  `downgrade_to_source_based`.
- `source_based` accepts only when its full `source_range` resolves to source
  chunks; otherwise it suggests `mark_unverified`.
- `invented_for_adaptation` is valid when it does not carry a quote or
  `source_range`; if it claims source text, validation returns an error and
  suggests `clear_quote`.

`resolved`, `verbatim_ok`, and `suggested_action` are code-owned verdict fields,
not model output fields. PR-104 does not implement citation consistency,
pipeline mutation, status logging, fuzzy matching, similarity scoring, or LLM
judgment.

### Source Validation Step

PR-108 adds a runtime validation step without changing the V1 schema fields.

`backend/app/validation/pipeline_step.py` exposes
`run_source_validation_step(output, retrieval_context, store)`. The function:

- deep-copies the output before applying code-owned repairs;
- validates every discovered `SourceLink` with `validate_source_link`;
- checks every discovered `EvidenceMeta` with `check_citation_consistency`;
- aggregates all findings into a `ValidationReport`;
- returns `SourceValidationStepResult` with the updated output, validation
  report, and recorded changes.

`SourceValidationChange` records the path, action, before value, after value,
and originating finding code for each code-made repair. These records are step
results only in W1. They are not `AdaptationLogEntry` records and are not
persisted into `Episode.adaptation_log` until a later project-state layer owns
that write.

PR-108 remains pure runtime validation: it does not add a business agent, fixed
pipeline module, LLM call, database, vector store, API endpoint, UI highlight
rendering, or new model-output field.

### IP Diagnosis And Story Bible

PR-201 adds schema support for W2 IP asset generation while keeping all new
fields optional at the project level.

`ScoredItem` stores one normalized score and an evidence-bound rationale:

- `score: float` in the inclusive range `[0, 1]`
- `rationale: EvidenceText`

`IPDiagnosis` stores F6 diagnosis output:

- `adaptation_type: EvidenceText`
- `core_conflict_strength: ScoredItem`
- `protagonist_desire_clarity: ScoredItem`
- `oppression_structure: ScoredItem`
- `reversal_potential: ScoredItem`
- `vertical_fit: ScoredItem`
- `production_cost_risk: ScoredItem`
- `compliance_risk_notes: list[EvidenceText]`
- `recommended_profile_id: str`

`recommended_profile_id` is a model field here only. W2 task-level validation
will later verify that it points to a real profile id.

`StoryBible` keeps its existing W0 fields and adds only one optional field:

- `core_hook: EvidenceText | None = None`

`ShortDramaProject` adds:

- `ip_diagnosis: IPDiagnosis | None = None`

PR-201 does not add generation logic, business agents, LLM calls, persistence,
API endpoints, W3 episode/script models, or changes to the nested episode graph.

## 5. Episode Contract

Each V1 `Episode` requires the short-drama core fields:

- `source_ranges`
- `opening_hook`
- `main_conflict`
- `emotional_payoff`
- `cliffhanger`
- `scenes`

Episode-level optional support objects include:

- `retention_points`
- `fidelity`
- `quality_checks`
- `visual_layer`
- `forks`
- `adaptation_log`

PR-106 makes `Episode.source_ranges` operational for F8 source binding:

- `bind_source_ranges(episode, source_links, store)` writes an ordered,
  non-empty `list[SourceLink]` into `episode.source_ranges`.
- Any `SourceLink.source_range` that is present must fully resolve through
  `EvidenceStore` by `chapter_id` and paragraph range. Unresolvable ranges
  raise a clear error instead of creating a dangling binding.
- `invented_for_adaptation` links with `source_range=None` are preserved in
  order and resolve to `resolved_text=None`.
- `resolve_episode_sources(episode, store)` returns ordered segment data:
  `source_link`, `source_range`, `resolved_text`, and `source_type`.
- F8 stores only backend binding and resolution data. It does not change the
  nested Episode schema, render F14 UI, call an LLM, or add persistence.

## 6. Scene, Beat, And Element

`Scene` contains source links, optional visual notes, and nested beats.
`Beat` contains ordered elements.

`Element` is a discriminated union keyed by `type`. PR-004 defines these element
types:

- `action`
- `dialogue`
- `performance`
- `sound`
- `transition`
- `title_card`

This creates a typed shape for script output without implementing any business
agent, LLM generation, retrieval, validation pipeline, or API endpoint.
