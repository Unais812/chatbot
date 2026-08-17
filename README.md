# AI Chatbot with Claude Agent SDK

This project features a chatbot I built as part of my MLOps learning journey. It uses the Claude Agent SDK as the agent, with two tools integrated for document retrieval and live web search, and the full request cycle tracing through Arize Phoenix

## Overview

The agent runs on the Claude Agent SDK and decides per query, whether to answer directly or call one of two tools:

- **Document retrieval** via ChromaDB, a vector database queried for relevant context from a seeded knowledge base
- **Web search** via Tavily, for information outside the knowledge base or that changes over time

Every decision made by the LLM is instrumented with OpenTelemetry and exported to Arize Phoenix, providing full visibility into which tool the agent chose, and the reasoning behind each choice made which gives useful insights as to how the system operates and also provides smooth debugging

The entire stack runs using Docker Compose as independent services on the same network

The chat UI is a simple HTML and JavaScript frontend, served by a FastAPI backend running on Uvicorn

## Architecture

```
┌─────────────┐        ┌──────────────┐
│   Browser   │◄──────►│  agent-app   │
│  (chat UI)  │  HTTP  │  (FastAPI +  │
└─────────────┘        │  Agent SDK)  │
                        └──────┬───────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 ▼             ▼             ▼
          ┌───────────┐  ┌──────────┐  ┌──────────┐
          │ ChromaDB  │  │  Tavily  │  │ Phoenix  │
          │ (vector   │  │ (web     │  │ (traces  │
          │  store)   │  │  search) │  │  + UI)   │
          └───────────┘  └──────────┘  └──────────┘
```



## Tech stack

| Component | Purpose |
|---|---|
| Claude Agent SDK | Agent loop, tool routing, model calls |
| FastAPI + Uvicorn | Web server serving the chat UI and API |
| ChromaDB | Vector store for document retrieval |
| Tavily | Web search API |
| Arize Phoenix | OpenTelemetry tracing and inspection UI |
| Docker Compose | Service orchestration |

## Prerequisites

- Docker and Docker Compose
- An Anthropic credential, either:
  - An API key from the [Claude Console](https://console.anthropic.com/account/keys), billed pay as you go, or
  - A Claude Pro or Max subscription, authenticated via `claude setup-token` (see below)
- A [Tavily](https://tavily.com) API key, free tier is sufficient

## Setup

1. Clone the repository and create a `.env` file in the project root.

2. Add your credentials to `.env`. Use one of the two Anthropic auth options, not both:

   ```
   # Option A, pay as you go API key
   ANTHROPIC_API_KEY=sk-ant-...

   # Option B, Claude Pro/Max subscription (run `claude setup-token` locally first)
   CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...

   TAVILY_API_KEY=tvly-...
   ```

3. Make sure `.env` is listed in `.gitignore`, it holds live credentials and should never be committed.

4. Build and start the core services:

   ```bash
   docker compose up --build
   ```

5. In a separate terminal, seed the knowledge base (one-time, or whenever you want to refresh the documents):

   ```bash
   docker compose --profile seed up seed
   ```

## Usage

Open `http://localhost:8080` in a browser and chat with the agent. Ask something that should hit the seeded knowledge base, and something that needs current information, to see both tools get exercised.

## Observability

Open `http://localhost:6006` for the Phoenix UI. Each conversation turn appears as a trace, expand one to see the root span for the query, child spans for any tool calls, and the exact input and output at each step, including latency and token counts.

## Project structure

```
.
├── chatbot.py          # Agent definition, tools, FastAPI server
├── seed.py              # One-time script to populate ChromaDB
├── index.html           # Chat UI served by the agent
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env                  # Not committed, holds API credentials
```

## Notes

- This project was built as a hands-on exercise, prioritising a working end to end pipeline over a production workload
- The agent holds a single shared session, so it is built for one conversation at a time, not concurrent users
