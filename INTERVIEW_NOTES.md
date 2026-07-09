# Interview Notes — mcp-rag-mini

Твои шпаргалки на случай, если рекрутер / инженер откроют этот репо и начнут задавать вопросы. Прочитай перед созвоном.

## Что ты покажешь одним предложением

> "Мини-RAG-сервис, где один и тот же ChromaDB-индекс отдаётся и через REST для классических клиентов, и через MCP-tool для LLM-агентов. Разделяю retrieval и generation — это разные SLO и разные метрики."

## Ключевые решения и почему

### 1. Почему две поверхности (REST + MCP), а не одна?

- **REST** — универсально: любой скрипт, дашборд, eval-harness.
- **MCP** — новый стандарт tool-use для LLM (Anthropic, 2024-2025). Один и тот же индекс отдаётся без промежуточного HTTP-клиента в промпте.
- **Общий `DocStore`** — нет двух источников правды.

### 2. Почему ChromaDB, а не pgvector/Weaviate/Pinecone?

- **Chroma**: embedded, персистентная, нулевой overhead на локальный dev. Подходит для 10K–1M векторов.
- **pgvector**: если уже есть Postgres — да. Здесь у меня нет — лишний контейнер.
- **Weaviate/Qdrant/Pinecone**: production-grade, но overkill для demo.
- **Cosine similarity + HNSW индекс** — стандарт для семантического поиска.

### 3. Почему `fastembed`, а не sentence-transformers?

- `fastembed` — ONNX runtime, ~5x быстрее на CPU и без torch (~1.5GB vs ~50MB).
- Для деплоя в контейнере это разница между 200MB и 2.5GB имиджем.

### 4. Фиксированный chunk с overlap — почему не семантический?

- Быстро объясняется, легко воспроизводится, работает "достаточно" для 80% случаев.
- В `INTERVIEW_NOTES` открыто пишу, что это интенционально упрощено. На интервью объясняю, что semantic/recursive chunking — следующий шаг, если нужен recall выше.

### 5. Почему нет LLM в этом сервисе?

- Retrieval и generation — разные SLO. Retrieval меряется по recall@k, latency, drift; generation — по faithfulness, toxicity, hallucination rate.
- Мешать их в одном сервисе — путь к монолиту, где непонятно, где именно пропала точность.
- Возвращаю `suggested_prompt` — клиент сам решает, куда его слать.

## Вопросы, которые тебе почти наверняка зададут

**Q: Как ты будешь масштабировать это на 100M документов?**
A: ChromaDB embedded до ~1M векторов ок. Дальше — переход на Chroma server / Qdrant / Weaviate. Отдельный embedding-worker (batching), очередь на upload (Redis Streams / SQS), горизонтальное шардирование индекса по doc_id.

**Q: Что будешь делать с hallucinations?**
A: На стороне ретривала — reranker (cross-encoder BGE-reranker-base), фильтр по score threshold. На стороне генерации — force LLM цитировать `[chunk_id]` и валидировать в постпроцессинге. Плюс eval-harness с ragas / trulens.

**Q: Как обновлять embeddings, если поменял модель?**
A: Полный re-embed индекса. Модель фиксируется в metadata коллекции; при mismatch запускаем миграцию: параллельно новая коллекция → cutover → удаление старой.

**Q: Почему нет тестов?**
A: (Честно) Демо-уровень. В прод-версии добавил бы: unit на chunking, интеграционный на add→search round-trip с known-good pairs, eval-harness с фиксированным датасетом Q&A и tracking recall@k в CI.

**Q: Что было самое сложное?**
A: Не сложное, а — где легко ошибиться: правильно связать `doc_id` в metadata, чтобы `list_documents` работал через один запрос без дополнительной таблицы. И совместимость версий `chromadb` и `fastembed` (у обоих pinning ONNX runtime).

**Q: Почему MCP, а не Function Calling через OpenAI-style?**
A: OpenAI function calling — вендорлок под их API. MCP — открытый протокол (Anthropic), любой LLM-клиент, поддерживающий MCP (Claude Desktop, Cursor, custom agents), получает tool одинаково. Меньше glue-кода.

## Что ты честно НЕ знаешь (и это ок)

- Не помнишь наизусть все API HNSW-параметров ChromaDB (M, ef_construction). Скажи: "Настройки индекса в дефолте, для прода тюнил бы через recall@k on validation set."
- Не сравнивал fastembed vs sentence-transformers на конкретной задаче — просто выбрал за скорость на CPU.
- Не запускал под нагрузкой. Оценка тактильно: до 100 QPS на 4-core CPU для all-MiniLM.

## Как прогнать локально за 3 минуты

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.api:app --reload
```

Открой `http://localhost:8000/docs` — Swagger UI. Через него заапл интересные тебе доки (например, вставь текст любой статьи из своей коммерческой работы, sanitized).

Затем на созвоне ты можешь live-показать: "Вот я загрузил доку → вот я задал вопрос → вот верхние чанки → вот suggested prompt → скармливаю его в Claude." Это круче любого слайда.
