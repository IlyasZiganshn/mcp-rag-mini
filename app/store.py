"""Хранилище документов поверх ChromaDB + fastembed.

Одно место, где живут эмбеддинги и метаданные. И REST-API, и MCP-сервер ходят
через один и тот же экземпляр DocStore — так проще: одинаковые ответы и никаких
рассинхронов между двумя интерфейсами.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding


@dataclass
class Chunk:
    id: str
    text: str
    doc_title: str
    score: float


class DocStore:
    def __init__(self, persist_dir: str = "./chroma_data",
                 model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="docs",
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = TextEmbedding(model_name=model_name)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self.embedder.embed(texts)]

    def _chunk(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Наивное фиксированное окно с overlap. Для мини-RAG хватает —
        и понятно на интервью. Для прод-качества берут semantic/recursive chunking."""
        if not text.strip():
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end].strip())
            if end == len(text):
                break
            start = end - overlap
        return [c for c in chunks if c]

    def add_document(self, title: str, text: str) -> dict:
        chunks = self._chunk(text)
        if not chunks:
            return {"doc_id": None, "chunks": 0}
        doc_id = str(uuid.uuid4())
        ids = [f"{doc_id}::{i}" for i in range(len(chunks))]
        embeddings = self._embed(chunks)
        metadatas = [{"doc_id": doc_id, "doc_title": title, "chunk_ix": i}
                     for i in range(len(chunks))]
        self.collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return {"doc_id": doc_id, "chunks": len(chunks)}

    def search(self, query: str, top_k: int = 4) -> list[Chunk]:
        emb = self._embed([query])
        res = self.collection.query(
            query_embeddings=emb,
            n_results=top_k,
        )
        chunks: list[Chunk] = []
        for i in range(len(res["ids"][0])):
            chunks.append(Chunk(
                id=res["ids"][0][i],
                text=res["documents"][0][i],
                doc_title=res["metadatas"][0][i]["doc_title"],
                score=1.0 - float(res["distances"][0][i]),
            ))
        return chunks

    def list_documents(self) -> list[dict]:
        all_meta = self.collection.get(include=["metadatas"])
        seen: dict[str, dict] = {}
        for meta in all_meta.get("metadatas") or []:
            did = meta["doc_id"]
            if did not in seen:
                seen[did] = {"doc_id": did, "title": meta["doc_title"], "chunks": 0}
            seen[did]["chunks"] += 1
        return list(seen.values())
