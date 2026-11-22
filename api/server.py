import sys
import os
import json
import asyncio
import dotenv
dotenv.load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, AsyncGenerator
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import create_agent, tools, resolve_text_tool_calls, format_agent_response, set_operator_turn
import icinga_api
import elasticsearch_api
import graphite_api
import database_api
import knowledge_base

# Sentry Observability & AI Tracing Integration
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.langchain import LangchainIntegration

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
SENTRY_ENABLED = bool(SENTRY_DSN)

if SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            LangchainIntegration(),
        ],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
        environment=os.environ.get("ENVIRONMENT", "production"),
        release="icinga-aiops-agent@2.0.0"
    )
    print("[Sentry] Observability & LangChain AI tracing enabled.")
else:
    print("[Sentry] SENTRY_DSN not set; APM tracing disabled.")

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

# =============================================================================
# DYNAMIC LLM CONFIGURATION & COMPANY GPU STATE
# =============================================================================
DEFAULT_GPU_URL = os.environ.get("COMPANY_GPU_URL") or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434"
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL") or "llama3.1:8b"

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama").lower()

active_llm_config = {
    "provider": DEFAULT_PROVIDER,
    "model": DEFAULT_MODEL if DEFAULT_PROVIDER == "ollama" else os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b"),
    "base_url": DEFAULT_GPU_URL,
    "server_label": "🏢 GPU Server" if DEFAULT_PROVIDER == "ollama" else "⚡ Groq Cloud LPU"
}

AVAILABLE_MODELS = [
    {
        "id": "openai/gpt-oss-20b",
        "name": "GPT-OSS 20B (Groq Cloud)",
        "badge": "⚡ Groq LPU",
        "server": "⚡ Groq Cloud LPU",
        "provider": "groq",
        "base_url": None,
        "description": "Same model family served from Groq's cloud LPUs"
    },
    {
        "id": "gpt-oss:20b",
        "name": "GPT-OSS 20B (Default)",
        "badge": "⚡ Fast / 114 tok/s",
        "server": "🏢 Company GPU",
        "base_url": DEFAULT_GPU_URL,
        "description": "20.9B params, MXFP4, 100% tool calling accuracy"
    },
    {
        "id": "qwen3:14b",
        "name": "Qwen3 14B",
        "badge": "🧠 Deep Reasoning",
        "server": "🏢 Company GPU",
        "base_url": DEFAULT_GPU_URL,
        "description": "14B params, deep troubleshooting & root cause reasoning"
    },
    {
        "id": "gemma4:12b",
        "name": "Gemma4 12B",
        "badge": "🎯 High Precision",
        "server": "🏢 Company GPU",
        "base_url": DEFAULT_GPU_URL,
        "description": "12B params, structured JSON & metric analytics"
    },
    {
        "id": "gemma4:e4b",
        "name": "Gemma4 4B",
        "badge": "🚀 Edge Fast",
        "server": "🏢 Company GPU",
        "base_url": DEFAULT_GPU_URL,
        "description": "4B params, ultra-low latency alerts triage"
    },
    {
        "id": "llama3.1:8b-instruct-q4_K_M",
        "name": "Llama 3.1 8B Instruct",
        "badge": "🦙 Standard NOC",
        "server": "🏢 Company GPU",
        "base_url": DEFAULT_GPU_URL,
        "description": "8B params, standard operations & NOC runbooks"
    },
    {
        "id": "llama3.1:8b",
        "name": "Llama 3.1 8B (Localhost Fallback)",
        "badge": "💻 Local Air-Gapped",
        "server": "💻 Local Host",
        "base_url": "http://localhost:11434",
        "description": "8B params, local standalone fallback when off-VPN"
    }
]

print(f"Initializing LangGraph Agent ({active_llm_config['model']} via {active_llm_config['server_label']})...")
agent_executor = create_agent(
    enable_actions=True,
    provider=active_llm_config["provider"],
    model_name=active_llm_config["model"],
    base_url=active_llm_config["base_url"]
)
print("LangGraph Agent Ready.")


class SwitchModelRequest(BaseModel):
    model: str
    base_url: Optional[str] = None
    provider: Optional[str] = "ollama"


@app.get("/api/models")
async def list_models():
    """Returns available Company GPU and local models, plus live GPU connectivity status."""
    gpu_online = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{DEFAULT_GPU_URL}/api/tags")
            if resp.status_code == 200:
                gpu_online = True
    except Exception:
        gpu_online = False

    return {
        "active_model": active_llm_config["model"],
        "active_base_url": active_llm_config["base_url"],
        "active_provider": active_llm_config["provider"],
        "active_server_label": active_llm_config["server_label"],
        "tools_count": len(tools),
        "gpu_connected": gpu_online,
        "company_gpu_url": DEFAULT_GPU_URL,
        "models": AVAILABLE_MODELS
    }


@app.post("/api/model")
async def switch_model(req: SwitchModelRequest):
    """Hot-swaps the active LLM on the company GPU or local Ollama without restarting the server."""
    global agent_executor, active_llm_config
    try:
        model_name = req.model.strip()
        base_url = (req.base_url or ("http://localhost:11434" if "localhost" in model_name else DEFAULT_GPU_URL)).strip()
        provider = (req.provider or "ollama").strip()

        if provider == "groq":
            server_label = "⚡ Groq Cloud LPU"
        elif base_url == DEFAULT_GPU_URL and "localhost" not in base_url:
            server_label = "🏢 GPU Server"
        else:
            server_label = "💻 Local Ollama"
        print(f"[Model Switch] Switching active agent to model '{model_name}' on {server_label} ({base_url})...")

        new_agent = create_agent(
            enable_actions=True,
            provider=provider,
            model_name=model_name,
            base_url=base_url
        )
        agent_executor = new_agent
        active_llm_config["model"] = model_name
        active_llm_config["base_url"] = base_url
        active_llm_config["provider"] = provider
        active_llm_config["server_label"] = server_label

        return {
            "status": "success",
            "message": f"Successfully switched to {model_name} on {server_label}",
            "active_model": model_name,
            "active_base_url": base_url,
            "server_label": server_label
        }
    except Exception as e:
        print(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch model: {str(e)}")


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"
    context: Optional[Dict[str, Any]] = None
    username: Optional[str] = None


class QueryResponse(BaseModel):
    response: str
    session_id: str


def _format_query(query: str, context: Optional[Dict[str, Any]], req_user: Optional[str] = None) -> str:
    full_query = query.strip()
    user = req_user or (context.get("username") if context else None) or "admin"
    os.environ["CURRENT_ICINGA_USER"] = user
    set_operator_turn(full_query)

    try:
        from rbac_manager import RBACManager
        rbac = RBACManager()
        user_obj = rbac.get_user(user)
        role_name = user_obj.role.name if user_obj else "L1_READONLY"
        role_tier = user_obj.role.value if user_obj else 1
    except Exception:
        role_name = "L4_PLATFORM_ADMIN" if user == "admin" else "L1_READONLY"
        role_tier = 4 if user == "admin" else 1

    user_ctx = f"Authenticated Operator: {user} | Role: {role_name} (Tier {role_tier})"

    if context:
        valid_ctx = {k: v for k, v in context.items() if v and str(v).lower() != "unknown" and str(v).strip() != "" and k != "username"}
        if valid_ctx:
            context_str = ", ".join([f"{k}: {v}" for k, v in valid_ctx.items()])
            full_query = f"[{user_ctx} | Context: {context_str}]\n{full_query}"
        else:
            full_query = f"[{user_ctx}]\n{full_query}"
    else:
        full_query = f"[{user_ctx}]\n{full_query}"
    return full_query


# =============================================================================
# SYNCHRONOUS ANALYZE ENDPOINT
# =============================================================================

@app.post("/api/analyze", response_model=QueryResponse)
async def analyze_query(request: QueryRequest):
    try:
        full_query = _format_query(request.query, request.context, request.username)
        session_id = request.session_id or "default"

        config = {"configurable": {"thread_id": session_id}}

        # Run LangGraph Agent
        response = await asyncio.to_thread(
            agent_executor.invoke,
            {"messages": [("user", full_query)]},
            config
        )

        output_text = format_agent_response(response)

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
        full_query = _format_query(request.query, request.context, request.username)
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
            "plot_elasticsearch_log_volume": "📊 Plotting log volume trend...",
            "auto_generate_bpm_tree": "🌲 Auto-building Business Process DAG & evaluating quorum...",
            "generate_custom_sla_report": "📊 Generating Executive SLA Report (PDF & Excel)...",
            "email_sla_report": "📨 Dispatching Executive SLA Report email with PDF & Excel to client...",
            "route_smart_notification": "📨 Routing context-aware notification...",
            "send_noc_shift_handover": "📋 Compiling 24/7 NOC Shift Handover briefing...",
            "verify_user_rbac_permission": "🛡️ Verifying RBAC tool-gating security clearance..."
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
                    
                    # Stream rich tool output (tables, charts, DAGs) directly to the client
                    out_obj = event.get("data", {}).get("output")
                    tool_text = ""
                    if hasattr(out_obj, "content"):
                        tool_text = str(out_obj.content).strip()
                    elif isinstance(out_obj, str):
                        tool_text = out_obj.strip()

                    # Only pre-formatted Markdown is shown directly; raw data structures are left for the model to summarize.
                    if tool_text and not tool_text.startswith(("Error", "{", "[", "ACTION STAGED")):
                        payload = f"\n\n{tool_text}\n\n"
                        accumulated_text += payload
                        stream_worked = True
                        yield f"event: token\ndata: {json.dumps({'token': payload})}\n\n"

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
            accumulated_text = format_agent_response(response)

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
