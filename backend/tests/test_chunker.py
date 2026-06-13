from app.schema.short_drama import Registry, SourceChapter, SourceNovel


def sample_novel(*, second_paragraph: str = "Mira meets Rowan at the pier.") -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title="Harbor Case",
        chapters=[
            SourceChapter(
                chapter_id="CH001",
                title="Letter",
                paragraphs=[
                    "  Mira finds a sealed letter.  ",
                    second_paragraph,
                ],
            ),
            SourceChapter(
                chapter_id="CH002",
                title="Archive",
                paragraphs=["The archive lights flicker above Mira."],
            ),
        ],
    )


def sample_registry() -> Registry:
    return Registry.model_validate(
        {
            "characters": [
                {
                    "character_id": "C001",
                    "name": "Mira",
                    "aliases": ["Detective Mira"],
                },
                {"character_id": "C002", "name": "Rowan", "aliases": ["Ro"]},
            ],
            "locations": [
                {"location_id": "L001", "name": "pier", "aliases": ["old pier"]},
                {"location_id": "L002", "name": "archive", "aliases": []},
            ],
        }
    )


def test_chunking_is_deterministic():
    from app.rag.chunker import chunk_novel

    first = chunk_novel(sample_novel(), registry=sample_registry())
    second = chunk_novel(sample_novel(), registry=sample_registry())

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.chunk_id for chunk in first] == [
        "CH001:p1-1",
        "CH001:p2-2",
        "CH002:p1-1",
    ]


def test_chunk_has_chapter_para_and_hash():
    from app.rag.chunker import chunk_novel

    chunk = chunk_novel(sample_novel(), registry=sample_registry())[0]

    assert chunk.source_type == "novel"
    assert chunk.text == "Mira finds a sealed letter."
    assert chunk.metadata.chapter_id == "CH001"
    assert chunk.metadata.para_range == (1, 1)
    assert chunk.metadata.source_hash
    assert chunk.source_ref is not None
    assert chunk.source_ref.source_range is not None
    assert chunk.source_ref.source_range.chapter_id == "CH001"
    assert chunk.source_ref.source_range.start_para == 1
    assert chunk.source_ref.source_range.end_para == 1


def test_character_ids_filled_by_registry_match():
    from app.rag.chunker import chunk_novel

    chunks = chunk_novel(sample_novel(), registry=sample_registry())

    assert chunks[0].metadata.character_ids == ["C001"]
    assert chunks[1].metadata.character_ids == ["C001", "C002"]
    assert chunks[1].metadata.location_ids == ["L001"]
    assert chunks[2].metadata.character_ids == ["C001"]
    assert chunks[2].metadata.location_ids == ["L002"]


def test_llm_dependent_tags_left_empty_in_w1():
    from app.rag.chunker import chunk_novel

    chunk = chunk_novel(sample_novel(), registry=sample_registry())[0]

    assert chunk.metadata.event_tags == []
    assert chunk.metadata.conflict_type is None
    assert chunk.metadata.emotional_tone is None


def test_source_hash_changes_on_single_char_edit():
    from app.rag.chunker import chunk_novel

    original = chunk_novel(sample_novel(), registry=sample_registry())[1]
    edited = chunk_novel(
        sample_novel(second_paragraph="Mira meets Rowan at the pier!"),
        registry=sample_registry(),
    )[1]

    assert original.text != edited.text
    assert original.metadata.source_hash != edited.metadata.source_hash


def test_source_text_normalization_trims_only_boundaries():
    from app.rag.chunker import normalize_source_text, source_hash_for_text

    assert normalize_source_text("\n\u3000Mira   keeps punctuation!\t") == (
        "Mira   keeps punctuation!"
    )
    assert source_hash_for_text("  Mira   keeps punctuation!  ") == source_hash_for_text(
        "Mira   keeps punctuation!"
    )
    assert source_hash_for_text("Mira   keeps punctuation!") != source_hash_for_text(
        "Mira keeps punctuation!"
    )
