from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import anyio
import os
import chromadb
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    tool,
    create_sdk_mcp_server,
)
from tavily import TavilyClient
from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
tracer_provider = trace_sdk.TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))
ClaudeAgentSDKInstrumentor().instrument(tracer_provider=tracer_provider)

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))


@tool("web_search", "Search the web for current information not in the knowledge base", {"query": str})
async def web_search(args):
    results = tavily_client.search(query=args["query"], max_results=3)
    summaries = [f"{r['title']}: {r['content']}" for r in results["results"]]
    return {
        "content": [
            {"type": "text", "text": "\n\n".join(summaries) if summaries else "No results found."}
        ]
    }

chroma_client = chromadb.HttpClient(
    host=os.environ.get("CHROMA_HOST", "localhost"),
    port=int(os.environ.get("CHROMA_PORT", 8000)),
)
collection = chroma_client.get_or_create_collection(name="knowledge_base")


@tool("search_documents", "Search the internal knowledge base for relevant information", {"query": str})
async def search_documents(args):
    results = collection.query(
        query_texts=[args["query"]],
        n_results=3,
    )
    matches = results["documents"][0]
    return {
        "content": [
            {"type": "text", "text": "\n".join(matches) if matches else "No relevant documents found."}
        ]
    }


tools_server = create_sdk_mcp_server(
    name="knowledge-tools",
    version="1.0.0",
    tools=[search_documents, web_search],
)


agent = {}


@asynccontextmanager
async def lifespan(app):
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant with access to an internal knowledge base and web search.",
        mcp_servers={"knowledge": tools_server},
        allowed_tools=[
            "mcp__knowledge__search_documents",
            "mcp__knowledge__web_search",
        ],
    )
    async with ClaudeSDKClient(options=options) as client:
        agent["client"] = client
        yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


@app.get("/")
async def index():
    with open("index.html") as f:
        return HTMLResponse(f.read())


@app.post("/chat")
async def chat(req: ChatRequest):
    client = agent["client"]
    await client.query(req.message)

    reply = ""
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    reply += block.text

    return {"reply": reply}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

anyio.run(main)
