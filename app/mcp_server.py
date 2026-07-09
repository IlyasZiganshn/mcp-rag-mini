"""MCP-сервер поверх того же DocStore.

Регистрируем один tool `rag_search` — Claude/любой MCP-клиент вызывает его,
получает найденные чанки и уже сам решает, как использовать в ответе.

Запуск: `python -m app.mcp_server` (stdio-транспорт).
Подключение в Claude Desktop:
    "mcpServers": {"rag-mini": {"command": "python", "args": ["-m", "app.mcp_server"]}}
"""
from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .store import DocStore

store = DocStore()
server = Server("rag-mini")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="rag_search",
            description=(
                "Search the local RAG index for passages relevant to a natural-language "
                "query. Returns up to top_k chunks with source document titles and scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language question."},
                    "top_k": {"type": "integer", "default": 4, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "rag_search":
        raise ValueError(f"Unknown tool: {name}")

    query = arguments["query"]
    top_k = arguments.get("top_k", 4)
    chunks = store.search(query, top_k=top_k)

    if not chunks:
        return [TextContent(type="text", text="No relevant passages found.")]

    parts = [
        f"[{c.doc_title}] (score={c.score:.3f})\n{c.text}"
        for c in chunks
    ]
    return [TextContent(type="text", text="\n\n---\n\n".join(parts))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
