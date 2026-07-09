"""REST API поверх DocStore.

Три эндпоинта: upload, ask, list. Никакого LLM здесь — только retrieval.
Ответ /ask возвращает найденные чанки + suggested-prompt для внешнего LLM.
Так проще для интервью: показываешь чистый retrieval-слой отдельно от генерации.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .store import DocStore

app = FastAPI(title="mcp-rag-mini")
store = DocStore()


class UploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=4, ge=1, le=20)


@app.post("/documents")
def upload_document(payload: UploadRequest):
    result = store.add_document(payload.title, payload.text)
    if not result["doc_id"]:
        raise HTTPException(400, "Empty document after chunking")
    return result


@app.get("/documents")
def list_documents():
    return {"documents": store.list_documents()}


@app.post("/ask")
def ask(payload: AskRequest):
    chunks = store.search(payload.question, top_k=payload.top_k)
    if not chunks:
        return {"answer_context": [], "suggested_prompt": None}

    context = "\n\n---\n\n".join(
        f"[{c.doc_title}] {c.text}" for c in chunks
    )
    prompt = (
        "Answer the question using only the context below. "
        "If the answer isn't in the context, say so.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {payload.question}\n\nAnswer:"
    )
    return {
        "answer_context": [
            {"doc_title": c.doc_title, "text": c.text, "score": c.score}
            for c in chunks
        ],
        "suggested_prompt": prompt,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
