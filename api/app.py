# FastAPI application entry point for the log investigation assistant.
#
# This file is the network layer of the project. It exposes the REST endpoints used by the browser UI,
# the local frontend, and any other client that wants to query the log assistant. Internally it delegates
# to the retrieval and orchestration modules so the API remains thin and reusable.

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from ingestion.ingest_logs import ensure_logs_ingested, ingest_logs
from orchestration.agent_graph import handle_agent_feedback, run_log_agent, stream_log_agent
from orchestration.log_search_graph import run_log_search_graph
from vectordb.chroma_client import ChromaVectorDB


class QueryRequest(BaseModel):
    """Request body used for search and chat endpoints."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class IngestRequest(BaseModel):
    """Request body for data re-ingestion operations."""

    reset_db: bool = False


app = FastAPI(title="Vector Log AI API", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    # Basic service liveness check used by deployment monitors and frontend health checks.
    return {"status": "ok", "service": "vector-log-ai-poc"}


@app.get("/api/logs/count")
def get_log_count() -> dict:
    # Return the current count of vectorized log entries stored in ChromaDB.
    return {"count": ChromaVectorDB().count()}


@app.post("/api/search")
def search_logs(payload: QueryRequest) -> dict:
    # Direct retrieval endpoint used when a client wants the raw search results without the agent layer.
    results = run_log_search_graph(payload.query, top_k=payload.top_k)
    documents = results.get("documents", [[]])[0] if results.get("documents") else []
    return {
        "query": payload.query,
        "count": len(documents),
        "results": results,
    }


@app.post("/api/ingest")
def ingest_logs_endpoint(payload: IngestRequest) -> dict:
    # Trigger log ingestion, optionally clearing the vector database first.
    if payload.reset_db:
        ingest_logs(reset_db=True)
    else:
        ensure_logs_ingested()
    return {"status": "success", "reset_db": payload.reset_db}


@app.post("/api/agent/chat")
def agent_chat(payload: QueryRequest) -> dict:
    # Typical synchronous chat route: one final answer is returned after the agent completes its work.
    response = run_log_agent(payload.query, top_k=payload.top_k)
    response["tool_results"] = response.get("tool_results", [])
    return response


class FeedbackRequest(BaseModel):
    """User-supplied feedback about whether the answer was helpful or not."""

    query: str = Field(..., min_length=1)
    reaction: str = Field(default="neutral")
    message: str = None


@app.post("/api/agent/feedback")
def agent_feedback(payload: FeedbackRequest) -> dict:
    # Record if the answer was liked or disliked and optionally refine the response.
    return handle_agent_feedback(payload.query, payload.reaction, payload.message)


@app.post("/api/agent/stream")
def agent_chat_stream(payload: QueryRequest):
    # Stream the agent's answer as SSE so the web UI can render incremental content while generating it.
    return StreamingResponse(stream_log_agent(payload.query, top_k=payload.top_k), media_type="text/event-stream")


@app.get("/chat", response_class=HTMLResponse)
def chat_ui() -> HTMLResponse:
    # Serve the browser UI that consumes the streaming endpoint and shows reasoning, metrics, and tool output.
    template = Path(__file__).resolve().parent / "templates" / "chat.html"
    return HTMLResponse(content=template.read_text())


@app.get("/")
def root() -> dict:
    # Simple root endpoint used for smoke checks and local developer navigation.
    return {"message": "Vector Log AI API is running", "docs": "/docs", "chat": "/chat"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=False)
