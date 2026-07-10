"""Unit tests for chunking. Runs without ChromaDB / fastembed installed."""
import sys
import types

# Stub external deps so importing app.store does not require them installed.
sys.modules.setdefault("chromadb", types.SimpleNamespace(
    PersistentClient=lambda **_: types.SimpleNamespace(
        get_or_create_collection=lambda **__: None,
    ),
))
sys.modules.setdefault("chromadb.config", types.SimpleNamespace(
    Settings=lambda **_: None,
))
sys.modules.setdefault("fastembed", types.SimpleNamespace(
    TextEmbedding=lambda **_: None,
))

from app.store import DocStore  # noqa: E402


def test_chunk_short_text_single_chunk():
    chunks = DocStore._chunk(None, "hello world")
    assert chunks == ["hello world"]


def test_chunk_empty_returns_empty():
    assert DocStore._chunk(None, "") == []
    assert DocStore._chunk(None, "   ") == []


def test_chunk_long_text_multiple_chunks_with_overlap():
    text = "a" * 1200
    chunks = DocStore._chunk(None, text, chunk_size=500, overlap=50)
    assert len(chunks) >= 3
    assert all(len(c) <= 500 for c in chunks)


def test_chunk_overlap_preserves_context():
    text = "Bitcoin. " + ("filler. " * 100) + "Whitepaper."
    chunks = DocStore._chunk(None, text, chunk_size=300, overlap=50)
    joined = "".join(chunks)
    assert "Bitcoin" in joined
    assert "Whitepaper" in joined
