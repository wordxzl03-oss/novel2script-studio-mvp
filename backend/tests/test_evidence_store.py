from app.rag.chunker import chunk_novel
from app.schema.short_drama import Registry, SourceChapter, SourceNovel


def sample_novel() -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title="Harbor Case",
        chapters=[
            SourceChapter(
                chapter_id="CH001",
                title="Letter",
                paragraphs=[
                    "Mira finds a sealed letter.",
                    "Mira meets Rowan at the pier.",
                    "Rowan hides the letter in the archive.",
                ],
            )
        ],
    )


def sample_registry() -> Registry:
    return Registry.model_validate(
        {
            "characters": [
                {"character_id": "C001", "name": "Mira", "aliases": []},
                {"character_id": "C002", "name": "Rowan", "aliases": []},
            ],
            "locations": [
                {"location_id": "L001", "name": "pier", "aliases": []},
                {"location_id": "L002", "name": "archive", "aliases": []},
            ],
        }
    )


def sample_chunks():
    return chunk_novel(sample_novel(), registry=sample_registry())


def test_add_and_get_chunk():
    from app.rag.evidence_store import EvidenceStore

    chunks = sample_chunks()
    store = EvidenceStore()

    store.add_chunks(chunks)

    assert store.get("CH001:p1-1") == chunks[0]
    assert store.get("missing") is None


def test_get_by_range_returns_overlapping_in_order():
    from app.rag.evidence_store import EvidenceStore

    chunks = sample_chunks()
    store = EvidenceStore()
    store.add_chunks([chunks[2], chunks[0], chunks[1]])

    result = store.get_by_range("CH001", (2, 3))

    assert [chunk.chunk_id for chunk in result] == ["CH001:p2-2", "CH001:p3-3"]


def test_list_by_character_tag():
    from app.rag.evidence_store import EvidenceStore

    store = EvidenceStore()
    store.add_chunks(sample_chunks())

    result = store.list_by_tag(character_id="C002")

    assert [chunk.chunk_id for chunk in result] == ["CH001:p2-2", "CH001:p3-3"]


def test_store_json_roundtrip_preserves_queries():
    from app.rag.evidence_store import EvidenceStore

    store = EvidenceStore()
    store.add_chunks(sample_chunks())

    data = store.to_json()
    restored = EvidenceStore.from_json(data)

    assert set(data) == {"chunks"}
    assert restored.get("CH001:p1-1") == store.get("CH001:p1-1")
    assert [chunk.chunk_id for chunk in restored.get_by_range("CH001", (2, 3))] == [
        "CH001:p2-2",
        "CH001:p3-3",
    ]
    assert [chunk.chunk_id for chunk in restored.list_by_tag(character_id="C002")] == [
        "CH001:p2-2",
        "CH001:p3-3",
    ]


def test_rag_package_exports_store_and_indexer():
    from app.rag import EvidenceIndex, EvidenceStore, build_inverted_index

    assert EvidenceStore
    assert EvidenceIndex
    assert build_inverted_index
