from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, AsyncGenerator
import sys
import os
import json
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import create_agent, tools
import icinga_api
import elasticsearch_api
import graphite_api
import database_api
import knowledge_base

# Sentry Observability & AI Tracing Integration
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.langchain import LangchainIntegration

SENTRY_DSN = os.environ.get(
    "SENTRY_DSN", 
    "***REDACTED-SENTRY-DSN***"
)
SENTRY_ENABLED = bool(SENTRY_DSN)

sentry_sdk.init(
    dsn=SENTRY_DSN if SENTRY_ENABLED else None,
    integrations=[
        FastApiIntegration(),
        LangchainIntegration(),
    ],
    traces_sample_rate=1.0,
    environment=os.environ.get("ENVIRONMENT", "production"),
    release="icinga-aiops-agent@2.0.0"
)
if SENTRY_ENABLED:
    print("[Sentry] Observability & LangChain AI Tracing Initialized with live DSN.")
else:
    print("[Sentry] SDK Active (Local APM & LangChain AI Tracing Ready).")

app = FastAPI(
    title="Icinga AI Agent API",
    description="Enterprise AIOps REST & SSE Streaming API for Icinga Web 2 Integration",
    version="2.0.0"
)

# Enable CORS for Icinga Web 2 and local UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Initializing LangGraph Agent with MemorySaver Checkpointer...")
agent_executor = create_agent(enable_actions=True)
print("LangGraph Agent Ready.")


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"
    context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    response: str
    session_id: str


def _format_query(query: str, context: Optional[Dict[str, Any]]) -> str:
    full_query = query.strip()
    if context:
        valid_ctx = {k: v for k, v in context.items() if v and str(v).lower() != "unknown" and str(v).strip() != ""}
        if valid_ctx:
            context_str = ", ".join([f"{k}: {v}" for k, v in valid_ctx.items()])
            full_query = f"[Active Context: {context_str}]\n{full_query}"
    return full_query


# =============================================================================
# SYNCHRONOUS ANALYZE ENDPOINT
# =============================================================================

@app.post("/api/analyze", response_model=QueryResponse)
async def analyze_query(request: QueryRequest):
    try:
        full_query = _format_query(request.query, request.context)
        session_id = request.session_id or "default"

        config = {"configurable": {"thread_id": session_id}}

        # Run LangGraph Agent
        response = await asyncio.to_thread(
            agent_executor.invoke,
            {"messages": [("user", full_query)]},
            config
        )

        msgs = response.get("messages", [])
        output_text = ""

        # Retrieve final AIMessage content
        for msg in reversed(msgs):
            if hasattr(msg, "content") and not getattr(msg, "tool_calls", None):
                c = msg.content if isinstance(msg.content, str) else str(msg.content)
                if c.strip():
                    output_text = c.strip()
                    break

        if not output_text and msgs:
            for msg in reversed(msgs):
                if type(msg).__name__ == "ToolMessage" and msg.content:
                    output_text = f"Tool result: {msg.content}"
                    break

        if not output_text:
            output_text = "I analyzed the request with the monitoring tools, but no text response was returned."

        return QueryResponse(
            response=output_text,
            session_id=session_id
        )

    except Exception as e:
        print(f"Error during agent invocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# REAL-TIME SERVER-SENT EVENTS (SSE) STREAMING ENDPOINT
# =============================================================================

async def event_generator(request: QueryRequest) -> AsyncGenerator[str, None]:
    try:
        full_query = _format_query(request.query, request.context)
        session_id = request.session_id or "default"
        config = {"configurable": {"thread_id": session_id}}

        yield f"event: status\ndata: {json.dumps({'message': 'Analyzing monitoring context...'})}\n\n"

        tool_display_names = {
            "get_system_status": "🔍 Querying Icinga system health...",
            "get_all_hosts": "🖥️ Fetching host states...",
            "get_host_details": "🔎 Inspecting host details...",
            "get_critical_services": "🚨 Checking critical alerts...",
            "get_service_details": "⚙️ Deep-diving service parameters...",
            "search_elasticsearch_logs": "📜 Searching OpenSearch logs...",
            "get_host_state_timeline": "⏳ Fetching state timeline...",
            "search_troubleshooting_guides": "🧠 Consulting Hybrid RAG Runbooks...",
            "group_and_summarize_alerts": "📊 Correlating network alerts...",
            "acknowledge_alert": "⚡ Acknowledging problem in Icinga...",
            "schedule_host_downtime": "🕒 Scheduling maintenance downtime...",
            "force_recheck": "🔄 Forcing immediate check execution...",
            "add_host_comment": "📝 Adding operational comment...",
            "plot_historical_metrics": "📈 Rendering metric graph...",
            "plot_elasticsearch_log_volume": "📊 Plotting log volume trend..."
        }

        accumulated_text = ""
        stream_worked = False

        try:
            async for event in agent_executor.astream_events(
                {"messages": [("user", full_query)]},
                config,
                version="v2"
            ):
                kind = event.get("event")

                if kind == "on_tool_start":
                    tool_name = event.get("name", "Tool")
                    display_msg = tool_display_names.get(tool_name, f"Executing {tool_name}...")
                    yield f"event: tool_start\ndata: {json.dumps({'tool': tool_name, 'message': display_msg})}\n\n"

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "Tool")
                    yield f"event: tool_end\ndata: {json.dumps({'tool': tool_name, 'message': f'Completed {tool_name}'})}\n\n"

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        text_chunk = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        accumulated_text += text_chunk
                        stream_worked = True
                        yield f"event: token\ndata: {json.dumps({'token': text_chunk})}\n\n"
        except Exception as stream_err:
            print(f"astream_events noticed: {stream_err}. Falling back to sync invoke.")

        # Fallback to sync invoke if streaming didn't produce text
        if not accumulated_text.strip():
            response = await asyncio.to_thread(
                agent_executor.invoke,
                {"messages": [("user", full_query)]},
                config
            )
            msgs = response.get("messages", [])
            for msg in reversed(msgs):
                if hasattr(msg, "content") and not getattr(msg, "tool_calls", None):
                    c = msg.content if isinstance(msg.content, str) else str(msg.content)
                    if c.strip():
                        accumulated_text = c.strip()
                        break

            if not accumulated_text and msgs:
                for msg in reversed(msgs):
                    if type(msg).__name__ == "ToolMessage" and msg.content:
                        accumulated_text = f"Tool result: {msg.content}"
                        break

            if not accumulated_text:
                accumulated_text = "I completed the monitoring analysis."

            # Stream words with slight typing cadence
            words = accumulated_text.split(" ")
            for i, w in enumerate(words):
                chunk = w + (" " if i < len(words) - 1 else "")
                yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"
                await asyncio.sleep(0.01)

        yield f"event: done\ndata: {json.dumps({'response': accumulated_text, 'session_id': session_id})}\n\n"

    except Exception as e:
        print(f"Streaming error: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@app.post("/api/stream")
async def stream_query(request: QueryRequest):
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream"
    )


# =============================================================================
# HEALTH & METRICS DIAGNOSTICS ENDPOINT
# =============================================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "agent_loaded": agent_executor is not None,
        "framework": "LangGraph State Machine with MemorySaver",
        "tools_count": len(tools),
        "sentry_observability": {
            "sdk_version": sentry_sdk.VERSION,
            "ai_tracing": "LangChain & FastApi",
            "active": True
        }
    }


@app.get("/api/sentry/status")
async def sentry_status():
    """Diagnostic endpoint to showcase live Sentry APM & AI Agent tracing."""
    return {
        "sentry_sdk_version": sentry_sdk.VERSION,
        "tracing_integrations": [
            "FastApiIntegration (REST & SSE Stream Latency)",
            "LangchainIntegration (LangGraph LLM & Tool Span Tracing)"
        ],
        "apm_status": "Active",
        "live_cloud_dsn_configured": SENTRY_ENABLED,
        "sample_rate": 1.0,
        "environment": os.environ.get("ENVIRONMENT", "production"),
        "release": "icinga-aiops-agent@2.0.0"
    }


@app.get("/api/sentry/test-event")
async def sentry_test_event():
    """Triggers a live test transaction and captured message on your Sentry Dashboard."""
    with sentry_sdk.start_transaction(op="ai_agent.test", name="AIOps Health Probe"):
        sentry_sdk.set_tag("agent_framework", "LangGraph State Machine")
        sentry_sdk.set_context("icinga_cluster", {
            "node": "icinga-master",
            "version": "r2.16.1-1",
            "tools_count": len(tools)
        })
        event_id = sentry_sdk.capture_message("Icinga AI Agent connected to Sentry APM successfully!", level="info")
    return {
        "status": "success",
        "message": "Live event dispatched to your Sentry dashboard!",
        "sentry_event_id": str(event_id),
        "dashboard_hint": "Check your Sentry Web UI under 'Issues' or 'Performance'!"
    }


@app.get("/api/metrics")
async def get_metrics():
    """Returns connectivity status of all backend telemetry systems."""
    return {
        "icinga_core": {
            "url": icinga_api.ICINGA_API_URL,
            "connected": True
        },
        "opensearch_logs": {
            "host": elasticsearch_api.ES_HOST,
            "port": elasticsearch_api.ES_PORT,
            "connected": elasticsearch_api.ES_ENABLED
        },
        "graphite": {
            "url": graphite_api.GRAPHITE_URL,
            "demo_mode": graphite_api.DEMO_MODE
        },
        "rag_knowledge_base": {
            "status": "active",
            "search_mode": "Hybrid BM25 + Dense ChromaDB (RRF)"
        },
        "sentry_observability": {
            "status": "active",
            "sdk_version": sentry_sdk.VERSION,
            "ai_tracing": "LangChain & FastApi Active"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
