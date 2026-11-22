# Icinga AI Agent — Complete Technical Deep Dive

> **Author:** Muneeb Zia · **Date:** August 3, 2026
> **Purpose:** Full understanding of everything built, how it works, key concepts, and how to test it.

---

## Table of Contents

1. [Project Summary — The 30-Second Elevator Pitch](#1-project-summary--the-30-second-elevator-pitch)
2. [Architecture Diagram — The Big Picture](#2-architecture-diagram--the-big-picture)
3. [Infrastructure Setup — Docker & Icinga](#3-infrastructure-setup--docker--icinga)
4. [File-by-File Code Walkthrough](#4-file-by-file-code-walkthrough)
5. [Data Flow — What Happens When a User Asks a Question](#5-data-flow--what-happens-when-a-user-asks-a-question)
6. [Key Concepts & Design Patterns (Learning Section)](#6-key-concepts--design-patterns)
7. [Phase 1 → Phase 2 Evolution](#7-phase-1--phase-2-evolution)
8. [Complete Testing Guide](#8-complete-testing-guide)
9. [Current Capabilities Summary Table](#9-current-capabilities-summary-table)
10. [What's Next — Future Roadmap](#10-whats-next--future-roadmap)

---

## 1. Project Summary — The 30-Second Elevator Pitch

**What is this?** An AI-powered assistant that sits on top of an Icinga 2 monitoring system. Instead of clicking through dashboards, engineers ask questions in plain English — and the agent queries live APIs, searches historical databases, and even takes actions on the infrastructure.

**What makes it special?**
- Runs **100% locally** — no OpenAI, no cloud. Uses Ollama + Qwen 2.5-Coder (7B parameters)
- Not just a chatbot — it has **24 executable tools** that touch live infrastructure
- **Phase 1** = Read-only observability (see everything, touch nothing)
- **Phase 2** = Action-capable AIOps (acknowledge alerts, schedule downtime, force re-checks)
- RAG pipeline for **Root Cause Analysis** using internal troubleshooting documentation
- **Human-in-the-Loop safety** — the agent always asks before modifying anything

**Tech Stack:**
| Layer | Technology |
|---|---|
| LLM | Qwen 2.5-Coder:7B via Ollama (local) |
| Agent Framework | LangChain (ReAct pattern) |
| Frontend | Streamlit |
| Monitoring Target | Icinga 2 (Dockerized) |
| Historical DB | MySQL IDO (Icinga Data Output) |
| Log Analytics | Elasticsearch (opensearch.internal:9200 — ready, pending VPN) |
| Time-Series | Graphite (demo mode) |
| RAG Vector DB | ChromaDB + HuggingFace `all-MiniLM-L6-v2` embeddings |
| Language | Python 3.10+ |

---

## 2. Architecture Diagram — The Big Picture

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                    USER LAYER                                            │
│                          👤 User types in Browser (localhost:8501)                        │
└────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                               FRONTEND: app.py (Streamlit)                               │
│  ┌─────────────────────┐  ┌────────────────────────┐  ┌────────────────────────────────┐ │
│  │  Sidebar Controls    │  │  Chat Interface        │  │  HITL Safety System            │ │
│  │  • Action Mode Toggle│  │  • Chat history        │  │  • Detect "Shall I proceed?"   │ │
│  │  • Data Source Status│  │  • Markdown rendering   │  │  • Render ✅/❌ buttons        │ │
│  │  • Tool Count Display│  │  • Inline image support │  │  • Inject user confirmation    │ │
│  └─────────────────────┘  └────────────────────────┘  └────────────────────────────────┘ │
└────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                         │ agent_executor.invoke({"input": prompt})
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                          AGENT CORE: agent.py (LangChain)                                │
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  LLM: Qwen 2.5-Coder:7B (via Ollama, temperature=0.0)                            │   │
│  │                                                                                    │   │
│  │  ReAct Loop:                                                                       │   │
│  │    Thought → Action → Observation → Thought → ... → Final Answer                  │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  24 Registered Tools:                                                                    │
│  ┌─────────────────┐ ┌───────────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ 10 READ Tools    │ │ 5 READ Extension  │ │ 2 ES Tools   │ │ 6 ACTION Tools       │    │
│  │ (Phase 1 Core)   │ │ (Phase 1 Ext)     │ │ (ES-Powered) │ │ (Phase 2)            │    │
│  └────────┬─────────┘ └────────┬──────────┘ └──────┬───────┘ └──────────┬───────────┘    │
└───────────┼────────────────────┼───────────────────┼────────────────────┼────────────────┘
            │                    │                   │                    │
            ▼                    ▼                   ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐
│  icinga_api.py   │ │ database_api.py  │ │elasticsearch_api │ │   icinga_actions.py      │
│  10 GET functions │ │ MySQL IDO queries│ │ 5 ES functions   │ │   6 POST functions       │
│                  │ │                  │ │ (ES_ENABLED flag)│ │   (Actions API)          │
│  knowledge_base  │ │ graphite_api.py  │ │                  │ │                          │
│  (RAG/ChromaDB)  │ │ (Demo metrics)   │ │                  │ │                          │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘ └──────────┬───────────────┘
         │                    │                    │                      │
         ▼                    ▼                    ▼                      ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐
│  🐋 Docker        │ │  🐋 Docker        │ │  📊 Production   │ │  🐋 Docker               │
│  Icinga 2 API    │ │  MySQL :3306     │ │  ES :9200        │ │  Icinga 2 Actions API    │
│  :5665 (HTTPS)   │ │  (IDO Schema)    │ │  (VPN Required)  │ │  :5665 (HTTPS POST)      │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────────────┘
```

**Data flows in ONE direction:**
```
User → Streamlit → LangChain Agent → LLM reasons → Agent calls Tool → Tool hits API → Data returns → LLM synthesizes → Streamlit renders
```

---

## 3. Infrastructure Setup — Docker & Icinga

### 3.1 Docker Container — The Monitoring Lab

The entire Icinga 2 instance runs in a single Docker container defined in `docker-compose.yaml`:

```yaml
services:
  icinga2:
    image: jordan/icinga2:latest
    container_name: icinga-lab
    hostname: icinga-master
    ports:
      - "80:80"     # Icinga Web 2 UI
      - "443:443"   # HTTPS
      - "5665:5665" # Icinga 2 REST API ← This is what our agent talks to
      - "3306:3306" # MySQL IDO Database ← Historical data
    environment:
      - ICINGAWEB2_ADMIN_USER=admin
      - ICINGAWEB2_ADMIN_PASS=admin123
```

**Key ports to remember:**
- **`:5665`** — The Icinga 2 REST API. This is the primary data source. All `icinga_api.py` and `icinga_actions.py` functions call this.
- **`:3306`** — MySQL database with the IDO (Icinga Data Output) schema. Contains historical state changes, downtime records, and notification logs.
- **`:80`** — Icinga Web 2 dashboard (you can login with `admin/admin123` to visually verify what the agent reports).

### 3.2 API Authentication

Icinga 2 uses HTTP Basic Auth over HTTPS with a self-signed certificate:

```python
# In icinga_api.py
ICINGA_API_URL = "https://localhost:5665/v1"
AUTH = ("root", "d74577114a85d55e")  # Pre-configured API user
```

> **Why `verify=False`?** The Docker container uses a self-signed SSL certificate. In production you'd use proper certificates, but for a dev lab we disable SSL verification. That's why we also call `urllib3.disable_warnings()`.

---

## 4. File-by-File Code Walkthrough

### Complete Project File Map

```
Icinga_AI_Agent/
├── docker-compose.yaml      # Infrastructure — Icinga 2 Docker container
├── requirements.txt          # All Python dependencies (15 packages)
│
├── app.py                    # FRONTEND — Streamlit chat UI + HITL safety
├── agent.py                  # BRAIN — LangChain ReAct agent + 24 tool definitions
│
├── icinga_api.py             # READ — 10 functions hitting Icinga REST API (GET)
├── icinga_actions.py         # WRITE — 6 functions hitting Icinga Actions API (POST)
├── database_api.py           # HISTORY — MySQL IDO queries + ES delegation
├── elasticsearch_api.py      # LOGS — 5 Elasticsearch functions (ready for prod)
├── graphite_api.py           # METRICS — Time-series data (demo mode)
├── knowledge_base.py         # RAG — ChromaDB + HuggingFace embeddings
│
├── chroma_db/                # Vector database storage (auto-generated)
│
├── docs/
│   ├── sample_troubleshooting.md      # RAG source — troubleshooting procedures
│   ├── use_cases_readonly_agent.md    # Documentation — 12 READ use cases
│   ├── use_cases_action_agent.md      # Documentation — 6 ACTION use cases
│   ├── Phase2_Action_Roadmap.md       # Roadmap for Phase 2 features
│   └── graphite_integration_explanation.md
│
├── Phase1_Documentation.md   # Original Phase 1 technical documentation
├── Icinga_Agent_Roadmap.md   # High-level project roadmap
└── README.md                 # Setup instructions
```

---

### 4.1 `icinga_api.py` — The Read-Only Eyes (10 Functions)

This module talks to the Icinga 2 REST API using **only GET requests**. It can see everything but cannot modify anything.

**The core helper pattern:**

```python
def _make_request(endpoint, method="GET", params=None, data=None):
    """Every function in this file calls this helper."""
    url = f"{ICINGA_API_URL}/{endpoint}"
    headers = {'Accept': 'application/json'}
    
    response = requests.request(
        method=method,
        url=url,
        auth=AUTH,           # HTTP Basic Auth tuple
        verify=False,        # Skip SSL verification (self-signed cert)
        headers=headers,
        params=params,       # URL query parameters
        json=data            # POST body (for filtered queries)
    )
    response.raise_for_status()
    return response.json()
```

> **🧠 Concept — Helper/Wrapper Pattern:** Instead of repeating the same `requests.get()` code in 10 functions, we write ONE helper that handles auth, SSL, headers, and error handling. Every function calls `_make_request("objects/hosts")` and the helper handles the rest. This is a fundamental **DRY (Don't Repeat Yourself)** pattern.

**The 10 functions and what API endpoints they hit:**

| # | Function | Icinga API Endpoint | What It Does |
|---|----------|-------------------|-------------|
| 1 | `get_system_status()` | `GET /v1/status/IcingaApplication` | Version, node name, HA status |
| 2 | `get_all_hosts(filter_state)` | `GET /v1/objects/hosts` | All hosts, optionally filtered by UP/DOWN |
| 3 | `get_host_details(hostname)` | `GET /v1/objects/hosts/{name}` | Templates, vars, state, check output |
| 4 | `get_critical_services()` | `POST /v1/objects/services` | Services where `state == 2` (CRITICAL) |
| 5 | `get_templates_and_zones()` | `GET /v1/objects/hosttemplates` | Available monitoring templates |
| 6 | `get_service_details(host, svc)` | `GET /v1/objects/services/{host}!{svc}` | Deep-dive into one service |
| 7 | `get_host_services(hostname)` | `POST /v1/objects/services` + filter | All services on a host |
| 8 | `get_notification_history(host)` | `GET /v1/objects/notifications` | Who gets notified and how |
| 9 | `get_downtime_status()` | `POST /v1/objects/hosts` + filter | Hosts/services in active downtime |
| 10 | `get_check_statistics()` | `GET /v1/status/CIB` | Latency, execution time, check counts |

**Important code snippet — Icinga state mapping:**

```python
# Icinga represents states as integers internally
# You'll see this pattern across multiple files
state_map = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}        # For hosts
state_map = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}  # For services
```

> **🧠 Concept — Icinga's `host!service` notation:** Icinga 2 identifies services as `hostname!servicename`. So "the SSH service on web-01" becomes `web-01!ssh`. You'll see this in the API URLs: `/v1/objects/services/web-01!ssh`.

**Interesting technique — Fallback query strategy:**

```python
def get_critical_services():
    # Try POST with filter body first (cleaner)
    payload = {"filter": "service.state == 2"}
    data = _make_request("objects/services", method="POST", data=payload)
    
    if "error" in data:
        # Fallback to GET with URL params if POST fails
        data = _make_request("objects/services", params={"filter": "service.state==2"})
```

> **🧠 Why two methods?** The Icinga API supports both GET params and POST body for filters. POST body is cleaner for complex filters, but some Icinga versions handle them differently. Having a fallback makes our code **resilient**.

---

### 4.2 `icinga_actions.py` — The Hands (6 Action Functions)

This is the **Phase 2** module — it sends `POST` requests to Icinga's **Actions API** to modify the system.

**Key design decision — Separate module:**

```
icinga_api.py     → READ-ONLY  (GET requests only)
icinga_actions.py → WRITE/MODIFY (POST requests to /v1/actions/*)
```

> **🧠 Concept — Separation of Concerns (Security Boundary):** We deliberately keep read and write operations in separate files. In production, you'd give the read-only module a restricted API user that CAN'T write, and the action module a separate user that CAN. If someone compromises the read module, they still can't modify your infrastructure.

**The 6 action functions:**

| # | Function | Icinga Actions Endpoint | Real-World Use |
|---|----------|----------------------|---------------|
| 1 | `acknowledge_problem()` | `POST /v1/actions/acknowledge-problem` | Stop repeated alerts for a known issue |
| 2 | `schedule_downtime()` | `POST /v1/actions/schedule-downtime` | Mute alerts during maintenance |
| 3 | `add_comment()` | `POST /v1/actions/add-comment` | Leave notes visible in dashboard |
| 4 | `remove_acknowledgement()` | `POST /v1/actions/remove-acknowledgement` | Re-enable alerts after premature ack |
| 5 | `send_custom_notification()` | `POST /v1/actions/send-custom-notification` | Force-alert the on-call team |
| 6 | `reschedule_check()` | `POST /v1/actions/reschedule-check` | Verify a fix immediately |

**Important code snippet — How Icinga filters work in actions:**

```python
def acknowledge_problem(hostname, service=None, ...):
    if service:
        # Target a SPECIFIC service on a host
        filter_str = f'host.name=="{hostname}" && service.name=="{service}"'
        obj_type = "Service"
    else:
        # Target the HOST itself
        filter_str = f'host.name=="{hostname}"'
        obj_type = "Host"

    payload = {
        "type": obj_type,        # "Host" or "Service"
        "filter": filter_str,    # Icinga filter expression
        "author": author,
        "comment": comment,
    }
    
    result = _action_request("actions/acknowledge-problem", payload)
```

> **🧠 Concept — Icinga Filter Expressions:** Icinga uses its own DSL (Domain-Specific Language) for filtering. `host.name=="web-01" && service.name=="ssh"` is NOT Python — it's an Icinga expression that the API server evaluates. You're building strings that another system interprets.

**Important code snippet — Epoch timestamps for downtime:**

```python
def schedule_downtime(hostname, start_time=None, duration_hours=2.0, ...):
    # Icinga requires Unix epoch timestamps (seconds since 1970-01-01)
    start_dt = datetime.now()
    end_dt = start_dt + timedelta(hours=duration_hours)
    
    start_epoch = int(start_dt.timestamp())   # e.g., 1737158400
    end_epoch = int(end_dt.timestamp())       # e.g., 1737165600
    duration_secs = end_epoch - start_epoch   # e.g., 7200
```

> **🧠 Concept — Epoch Timestamps:** Many APIs (Icinga, Kubernetes, AWS) use Unix epoch time instead of human-readable dates. Python's `datetime.timestamp()` converts a `datetime` object to epoch seconds. This is a universal concept you'll use everywhere.

---

### 4.3 `database_api.py` — The Memory (MySQL IDO)

This module talks directly to the MySQL database inside the Docker container. The Icinga IDO (Icinga Data Output) feature writes every state change, downtime, and notification to MySQL in real-time.

**Important code — The data source switch:**

```python
# This one environment variable switches the ENTIRE data pipeline
DATA_SOURCE = os.environ.get("DATA_SOURCE", "mysql")  # "mysql" or "elasticsearch"

def get_historical_outages(hostname, limit=5):
    # Strategy Pattern: same interface, different backend
    if DATA_SOURCE.lower() == "elasticsearch":
        import elasticsearch_api
        return elasticsearch_api.search_host_events(hostname, time_range="30d", limit=limit)
    
    # Default: MySQL
    conn = mysql.connector.connect(host="127.0.0.1", port=3306, ...)
    cursor.execute("""
        SELECT state_time, state, output 
        FROM icinga_statehistory 
        WHERE object_id = %s AND state != 0 
        ORDER BY state_time DESC LIMIT %s
    """, (object_id, limit))
```

> **🧠 Concept — Strategy Pattern:** The same function (`get_historical_outages`) can use completely different backends (MySQL vs Elasticsearch) based on a config flag. The caller doesn't know or care which backend is being used. This is a core design pattern in software engineering.

> **🧠 Concept — Parameterized Queries:** Notice `%s` placeholders in the SQL instead of f-strings. This prevents **SQL Injection** — one of the most critical security vulnerabilities in software. NEVER do `f"WHERE name = '{user_input}'"`.

---

### 4.4 `elasticsearch_api.py` — The Deep Archive (5 Functions)

Pre-configured for the production Elasticsearch instance at `opensearch.internal:9200`. Currently disabled (VPN required), but the code is complete and ready.

**Important code — The `ES_ENABLED` toggle pattern:**

```python
# Config-driven feature flag
ES_ENABLED = os.environ.get("ES_ENABLED", "false").lower() == "true"

def search_host_events(hostname, time_range="24h", limit=20):
    # Guard clause — returns a friendly message instead of crashing
    if not ES_ENABLED:
        return {
            "error": "Elasticsearch is not enabled yet.",
            "detail": "ES_ENABLED is False. The production Elasticsearch at opensearch.internal:9200 "
                       "is not yet connected (VPN issue). Using MySQL IDO fallback.",
            "fallback": "mysql_ido"
        }
    
    # Lazy client initialization
    client = _get_client()
    if not client:
        return _not_connected_response("search_host_events")
    
    # Elasticsearch Query DSL
    query = {
        "size": limit,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {
            "bool": {
                "must": [
                    {"match": {"host.name": hostname}},
                    {"range": {"@timestamp": {"gte": "now-24h"}}}
                ]
            }
        }
    }
    result = client.search(index="icinga2-*", body=query)
```

> **🧠 Concept — Feature Flags:** `ES_ENABLED` is a **feature flag** — a boolean that enables/disables an entire feature without changing code. This is how companies like Google and Netflix do gradual rollouts. You set `ES_ENABLED=true` in production when ready, and `false` in dev.

> **🧠 Concept — Lazy Initialization:** The `_get_client()` function creates the Elasticsearch connection only when first needed (not at import time). This means importing the module never fails, even if ES is unreachable. The `global _es_client` pattern caches the connection for reuse.

> **🧠 Concept — Elasticsearch Query DSL:** ES uses a JSON-based query language. `bool.must` = AND, `bool.should` = OR, `range` = comparison operators, `match` = fuzzy text search. This is the standard way to query Elasticsearch in every language (Python, Java, Go).

**All 5 ES functions:**

| # | Function | What It Queries |
|---|----------|----------------|
| 1 | `search_host_events(hostname)` | All events for a specific host |
| 2 | `get_alert_history(severity)` | Full alert history with optional severity filter |
| 3 | `search_logs_by_keyword(keyword)` | Free-text search across all Icinga log indices |
| 4 | `get_performance_data(hostname, metric)` | Time-series perfdata with date_histogram aggregation |
| 5 | `get_host_state_timeline(hostname)` | UP/DOWN state changes over time |

---

### 4.5 `knowledge_base.py` — The Brain's Library (RAG Pipeline)

This is where **AI Engineering** really shines. This module implements a **Retrieval-Augmented Generation (RAG)** pipeline.

**The complete flow:**

```python
# 1. EMBEDDING MODEL — converts text into 384-dimensional vectors
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
# "Host is down" → [0.012, -0.043, 0.891, ..., 0.234]  (384 numbers)

# 2. DOCUMENT LOADING — reads your troubleshooting markdown
with open("docs/sample_troubleshooting.md", 'r') as f:
    content = f.read()

# 3. SPLITTING — breaks document into chunks by ## headers
headers_to_split_on = [("##", "Header 2")]
markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
chunks = markdown_splitter.split_text(content)
# Result: separate chunks for "Host Down", "Disk Space Full", "CPU Load High"

# 4. VECTOR STORE — converts chunks to vectors and stores in ChromaDB
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,        # Uses all-MiniLM-L6-v2 to vectorize
    persist_directory="./chroma_db"  # Saved to disk, survives restarts
)

# 5. SIMILARITY SEARCH — when the agent needs help
def search_troubleshooting_guides(query, top_k=2):
    docs = db.similarity_search(query, k=top_k)
    # "nginx crashed" → finds "Alert: CPU Load High" section (closest match)
```

> **🧠 Concept — RAG (Retrieval-Augmented Generation):** The LLM doesn't know your company's internal procedures. RAG solves this by:
> 1. Converting your docs into mathematical vectors (embeddings)
> 2. Storing them in a vector database (ChromaDB)
> 3. When a question comes in, converting it to a vector too
> 4. Finding the docs with the closest vectors (cosine similarity)
> 5. Injecting those docs into the LLM's context, so it answers with YOUR data
> 
> This is THE most important technique in modern AI engineering. Every enterprise AI product uses some form of RAG.

> **🧠 Concept — Embeddings:** An embedding is a list of numbers (vector) that represents the *meaning* of text. "Host crashed" and "Server is down" will have similar vectors even though they use different words. The model `all-MiniLM-L6-v2` produces 384-dimensional vectors and runs locally — no API calls needed.

> **🧠 Concept — Cosine Similarity:** When you search ChromaDB, it calculates how "close" your query vector is to each stored vector. Vectors pointing in the same direction = similar meaning. This is the math behind semantic search.

**The RAG source document** (`docs/sample_troubleshooting.md`) contains real-world troubleshooting sections:

| Section | When It's Retrieved |
|---------|-------------------|
| General Troubleshooting Strategy | Broad queries like "help me fix this" |
| Alert: Host Down | Queries about DOWN hosts, unreachable servers |
| Alert: Disk Space Full | Queries about disk warnings, storage issues |
| Alert: CPU Load High | Queries about CPU spikes, performance issues |

---

### 4.6 `graphite_api.py` — The Time Machine (Metrics Visualization)

This module integrates with Graphite for time-series performance data. Currently runs in **demo mode** with mock data that simulates a realistic CPU spike.

```python
DEMO_MODE = True  # Set to False when using real Graphite

def _generate_mock_data(target_metric, from_time):
    """Simulates a CPU spike pattern for demos."""
    for i in range(24):  # 24 hourly data points
        if i in [17, 18, 19]:
            value = random.uniform(85.0, 98.0)   # Spike at hours 17-19!
        else:
            value = random.uniform(15.0, 35.0)    # Normal baseline
        datapoints.append([value, timestamp])
```

The visualization happens in `agent.py` using matplotlib:

```python
@tool
def plot_historical_metrics(hostname, metric_name):
    result = graphite_api.get_historical_data(target_metric)
    
    # Generate plot
    plt.plot(x_values, y_values, marker='o', linestyle='-', color='b')
    plt.title(f"Historical Trend: {metric_name.upper()} on {hostname}")
    
    # Convert to Base64 for inline display in Streamlit
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    # Return as markdown image — Streamlit renders it inline!
    return f"![Trend](data:image/png;base64,{image_base64})"
```

> **🧠 Concept — Base64 Image Encoding:** Instead of saving a file to disk, we encode the PNG image as a Base64 string and embed it directly in markdown. Streamlit interprets `![](data:image/png;base64,...)` and renders it as an actual image. This is a common trick for serving images without a file server.

---

### 4.7 `agent.py` — The Brain (LangChain + ReAct + Tools)

This is the **most important file** in the project. It connects the LLM to all the tools and orchestrates the reasoning.

**Step 1 — Tool Definition with the `@tool` Decorator:**

```python
from langchain_core.tools import tool

@tool
def get_all_hosts(filter_state: Optional[str] = None) -> str:
    """
    Queries all hosts in Icinga.
    Optionally filter by state: 'UP', 'DOWN', or 'UNREACHABLE'.
    Example: get_all_hosts(filter_state='DOWN')
    """
    return str(icinga_api.get_all_hosts(filter_state))
```

> **🧠 Concept — The `@tool` Decorator:** This is a LangChain decorator that registers a Python function as something the LLM is "allowed to call". LangChain reads the **function name**, **parameter names**, **type hints**, and **docstring** and passes all of that to the LLM. The LLM then decides whether to call it based on the user's question. The better your docstring, the smarter the LLM's tool selection.

**Step 2 — Tool Registry (Organized by Category):**

```python
# Read-Only Tools (Phase 1 Original) — 10 tools
read_tools_original = [get_system_status, get_all_hosts, get_host_details, 
                       get_historical_outages, get_recent_downtimes, 
                       get_critical_services, get_templates_and_zones,
                       search_troubleshooting_guides, group_and_summarize_alerts,
                       plot_historical_metrics]

# Read-Only Tools (Phase 1 Extension) — 5 tools
read_tools_extended = [get_service_details, get_host_services, 
                       get_notification_history, get_downtime_status, 
                       get_check_statistics]

# Elasticsearch-Powered Tools — 2 tools
elasticsearch_tools = [search_elasticsearch_logs, get_host_state_timeline]

# Action Tools (Phase 2) — 6 tools  
action_tools = [acknowledge_alert, schedule_host_downtime, add_host_comment,
                remove_alert_acknowledgement, send_notification, force_recheck]

# Combined — 24 total tools
tools = read_tools_original + read_tools_extended + elasticsearch_tools + action_tools
```

**Step 3 — The ReAct Prompt Template (How the LLM Reasons):**

```
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question
```

> **🧠 Concept — ReAct Framework (Reasoning + Acting):** This is a foundational AI agent pattern from a 2022 Google Research paper. Instead of the LLM guessing an answer, it:
> 1. **Thinks** about what data it needs
> 2. **Acts** by calling a tool
> 3. **Observes** the result
> 4. **Repeats** if more data is needed
> 5. **Answers** only when it has enough information
> 
> The key insight: the LLM is outputting TEXT that follows a specific format. LangChain pattern-matches on keywords like `Action:` and `Action Input:` to extract the tool call. The LLM isn't "running code" — it's generating text that LangChain interprets as instructions.

**The System Prompt — Safety Rules for Actions:**

```
🛡️ SAFETY RULE: For ANY action that modifies the monitoring system, you MUST:
1. First describe EXACTLY what you plan to do (which host, which service, what action).
2. Ask the user for explicit confirmation ("Shall I proceed?").
3. Only execute the action tool AFTER the user says yes/confirm/proceed.
4. After executing, report the result clearly.
```

**Step 4 — Agent Creation with Safety Controls:**

```python
def create_agent(enable_actions=True):
    # Choose tools based on mode
    if enable_actions:
        agent_tools = tools  # All 24 tools
    else:
        agent_tools = read_tools_original + read_tools_extended + elasticsearch_tools  # 17 tools

    # Initialize local LLM
    llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.0)
    
    # Create the agent
    agent = create_react_agent(llm, agent_tools, prompt)
    
    # Wrap in executor with safety limits
    agent_executor = AgentExecutor(
        agent=agent,
        tools=agent_tools,
        verbose=True,              # Prints Thought/Action/Observation to terminal
        handle_parsing_errors=True, # Recovers if LLM outputs malformed text
        max_iterations=7            # Prevents infinite loops
    )
```

> **🧠 Concept — `temperature=0.0`:** Temperature controls randomness. `0.0` = deterministic (same input gives same output every time). For a monitoring agent, you want consistency — not creative answers. For a poetry generator, you'd use `0.7-1.0`.

> **🧠 Concept — `handle_parsing_errors=True`:** Open-source LLMs sometimes output text that doesn't match the `Action: ... Action Input: ...` format. This flag tells LangChain to recover gracefully instead of crashing. Essential for production agents.

> **🧠 Concept — `max_iterations=7`:** Prevents the agent from looping forever. If it hasn't found an answer after 7 Thought→Action→Observation cycles, it stops and returns whatever it has. Without this, a confused LLM could loop infinitely.

---

### 4.8 `app.py` — The Face (Streamlit UI + HITL Safety)

**Sidebar — Mode Selection & Status Dashboard:**

```python
# Action mode toggle — controls whether action tools are loaded
action_mode = st.toggle("Enable Action Capabilities", value=False)

# When toggled, the agent is re-initialized with different tools
if action_mode != st.session_state.current_action_mode:
    del st.session_state["agent_executor"]  # Force re-creation
    st.session_state.agent_executor = create_agent(enable_actions=action_mode)
```

**Human-in-the-Loop (HITL) Safety — The Most Important UI Feature:**

```python
# After each agent response, check if it's asking for confirmation
action_indicators = [
    "shall i proceed",
    "would you like me to",
    "do you want me to",
    "should i go ahead",
    "confirm this action",
]

content_lower = output_text.lower()
if any(indicator in content_lower for indicator in action_indicators):
    st.warning("⚠️ **Action Confirmation Required**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, proceed"):
            # Injects "Yes, proceed" as a new user message
            st.session_state.chat_history.append(
                HumanMessage(content="Yes, proceed with the action.")
            )
            st.rerun()  # Triggers the agent to execute the action
    with col2:
        if st.button("❌ No, cancel"):
            st.session_state.chat_history.append(
                HumanMessage(content="No, do not execute the action.")
            )
            st.rerun()
```

> **🧠 Concept — Human-in-the-Loop (HITL):** This is a safety pattern where the AI proposes an action but a human must approve it before execution. It operates at TWO levels in our system:
> 1. **Prompt level:** The system prompt tells the LLM "you MUST ask before acting"
> 2. **UI level:** Streamlit renders buttons, so even if the LLM skips asking, the user still has a UI-level gate
> 
> Neither level is foolproof alone, but together they provide defense-in-depth.

---

## 5. Data Flow — What Happens When a User Asks a Question

Let's trace exactly what happens when a user types: **"Is there anything critical right now?"**

```
┌─ STEP 1: User Input ─────────────────────────────────────────────────┐
│ Streamlit captures text, wraps in HumanMessage, sends to agent      │
│ agent_executor.invoke({"input": "Is there anything critical?"})     │
└──────────────────────────────────────┬───────────────────────────────┘
                                       ↓
┌─ STEP 2: LLM Reasoning ─────────────────────────────────────────────┐
│ Qwen receives the prompt + list of 24 tool descriptions             │
│ Qwen outputs:                                                       │
│   Thought: The user wants to know about critical alerts. I should   │
│   use the get_critical_services tool to check for active criticals. │
│   Action: get_critical_services                                     │
│   Action Input: (none)                                              │
└──────────────────────────────────────┬───────────────────────────────┘
                                       ↓
┌─ STEP 3: LangChain Intercepts ──────────────────────────────────────┐
│ LangChain sees "Action: get_critical_services"                      │
│ Maps it to @tool def get_critical_services() in agent.py            │
│ Calls icinga_api.get_critical_services()                            │
└──────────────────────────────────────┬───────────────────────────────┘
                                       ↓
┌─ STEP 4: API Call ───────────────────────────────────────────────────┐
│ icinga_api.py sends:                                                │
│   POST https://localhost:5665/v1/objects/services                   │
│   Body: {"filter": "service.state == 2"}                            │
│   Auth: Basic root:d74577114a85d55e                                 │
│ Icinga returns JSON with critical services                          │
└──────────────────────────────────────┬───────────────────────────────┘
                                       ↓
┌─ STEP 5: Observation Injected ───────────────────────────────────────┐
│ LangChain takes the return value and feeds it back to Qwen:         │
│   Observation: {"total_critical": 2, "services": [                  │
│     {"host_name": "web-01", "service_name": "http", ...},           │
│     {"host_name": "db-master", "service_name": "disk", ...}         │
│   ]}                                                                │
└──────────────────────────────────────┬───────────────────────────────┘
                                       ↓
┌─ STEP 6: LLM May Loop (Optional) ───────────────────────────────────┐
│ Qwen: "Thought: I found 2 critical services. Let me search for     │
│ troubleshooting steps for these issues."                            │
│ Action: search_troubleshooting_guides                               │
│ Action Input: "http service critical web server"                    │
│ → RAG pipeline returns matching troubleshooting docs                │
│ Observation: "--- Section: Alert: CPU Load High --- ..."            │
└──────────────────────────────────────┬───────────────────────────────┘
                                       ↓
┌─ STEP 7: Final Answer ──────────────────────────────────────────────┐
│ Qwen: "Thought: I now know the final answer."                      │
│ Final Answer: "There are 2 critical services:                       │
│   1. HTTP on web-01 — Connection refused. Try restarting nginx.     │
│   2. Disk on db-master — 95% full. Check /var/log for log bloat."  │
└──────────────────────────────────────┬───────────────────────────────┘
                                       ↓
┌─ STEP 8: UI Renders ────────────────────────────────────────────────┐
│ Streamlit displays the markdown response in the chat bubble         │
│ Response is added to chat_history for context in future questions   │
└─────────────────────────────────────────────────────────────────────┘
```

**What an ACTION flow looks like (e.g., "Acknowledge the ping alert on web-01"):**

```
Step 1: User asks to acknowledge
Step 2: LLM reads the system prompt safety rule
Step 3: LLM outputs Final Answer (NOT an Action!): 
        "I'll acknowledge the ping problem on web-01. Shall I proceed?"
Step 4: Streamlit detects "Shall I proceed?" → renders ✅/❌ buttons
Step 5: User clicks ✅ → "Yes, proceed" injected as new message
Step 6: LLM sees confirmation → NOW calls Action: acknowledge_alert
Step 7: icinga_actions.py sends POST to Icinga
Step 8: LLM reports: "✅ Successfully acknowledged problem on web-01"
```

---

## 6. Key Concepts & Design Patterns

### 6.1 Python Concepts Used in This Project

| Concept | Where Used | What to Know |
|---------|-----------|-------------|
| **Decorators (`@tool`)** | `agent.py` | A function that wraps another function. `@tool` adds metadata that LangChain reads. |
| **Type Hints (`str`, `Optional[str]`, `Dict`)** | Everywhere | Tells Python (and the LLM!) what types a function expects. `Optional[str]` means "str or None". |
| **f-strings** | API URLs, filter expressions | `f"objects/hosts/{hostname}"` — string interpolation. Faster and cleaner than `.format()`. |
| **Context Managers (`with`)** | `knowledge_base.py` | `with open(file) as f:` ensures the file is closed even if an error occurs. |
| **Dictionary unpacking (`**kwargs`)** | `elasticsearch_api.py` | `Elasticsearch(**conn_kwargs)` — passes a dict as keyword arguments. |
| **Global state (`global _es_client`)** | `elasticsearch_api.py` | Module-level singleton pattern. Use sparingly — it's a trade-off between convenience and testability. |
| **Try/Except/Finally** | `database_api.py` | `finally:` block ensures the MySQL connection is always closed, even after errors. |
| **List comprehensions** | `icinga_api.py` | `hosts = [{"name": a.get("name")} for result in data]` — concise loop syntax. |
| **Ternary expressions** | `icinga_actions.py` | `target = f"{host}!{svc}" if svc else host` — one-line if/else. |
| **`if __name__ == "__main__":`** | Every file | Code that only runs when the file is executed directly, not when imported. Used for self-tests. |
| **`os.environ.get("KEY", default)`** | Config variables | Read environment variables with fallbacks. Core to 12-factor app configuration. |

### 6.2 AI Engineering Concepts

| Concept | What It Is | Where We Use It |
|---------|-----------|----------------|
| **LLM (Large Language Model)** | A neural network trained on text that can generate text. Qwen2.5-Coder is a 7-billion parameter model. | `agent.py` — the "brain" |
| **ReAct Framework** | Thought → Action → Observation loop. Forces the LLM to reason before acting. | `agent.py` prompt template |
| **Tool Calling / Function Calling** | Letting the LLM decide which Python function to call based on user intent. | `@tool` decorators in `agent.py` |
| **RAG (Retrieval-Augmented Generation)** | Injecting relevant documents into the LLM's context before generating an answer. | `knowledge_base.py` |
| **Embeddings** | Converting text into numerical vectors that capture semantic meaning. | `HuggingFaceEmbeddings("all-MiniLM-L6-v2")` |
| **Vector Database** | A database optimized for storing and searching vectors by similarity. | ChromaDB in `knowledge_base.py` |
| **Prompt Engineering** | Crafting the system prompt to control LLM behavior (safety rules, tool usage instructions). | The `template` string in `agent.py` |
| **Temperature** | Controls randomness. 0.0 = deterministic, 1.0 = creative. | `ChatOllama(temperature=0.0)` |
| **Context Window** | The maximum amount of text the LLM can "see" at once (~8K tokens for Qwen 7B). | Why we strip unnecessary JSON fields before returning data to the LLM |
| **HITL (Human-in-the-Loop)** | Requiring human approval before AI takes dangerous actions. | `app.py` confirmation buttons |
| **Feature Flags** | Config-driven toggles that enable/disable features without code changes. | `ES_ENABLED`, `DEMO_MODE`, `DATA_SOURCE` |

### 6.3 Software Engineering Patterns

| Pattern | What It Is | Where We Use It |
|---------|-----------|----------------|
| **DRY (Don't Repeat Yourself)** | Extract common logic into helper functions. | `_make_request()`, `_action_request()`, `_not_connected_response()` |
| **Strategy Pattern** | Same interface, different implementations based on config. | `database_api.py` — MySQL vs Elasticsearch backend |
| **Separation of Concerns** | Each file does ONE thing. | `icinga_api.py` = read, `icinga_actions.py` = write, `agent.py` = orchestration |
| **Graceful Degradation** | System works even when some components are unavailable. | ES disabled → returns fallback message instead of crash. Graphite unavailable → uses demo data. |
| **Defensive Programming** | Every function handles errors and never crashes the whole app. | `try/except` blocks everywhere, `handle_parsing_errors=True` |
| **Lazy Initialization** | Create expensive resources only when first needed. | `_get_client()` in `elasticsearch_api.py` |
| **Self-Test Pattern** | Every module has `if __name__ == "__main__":` test code. | You can test each module independently. |

---

## 7. Phase 1 → Phase 2 Evolution

```
Phase 1 Core         Phase 1 Extended       Phase 2
(Read-Only Base)     (More Read + ES)       (Actions + HITL)
─────────────────    ──────────────────     ──────────────────
icinga_api.py (5fn)  icinga_api.py (10fn)   icinga_api.py (10fn)
database_api.py      database_api.py*       database_api.py*
knowledge_base.py    knowledge_base.py      knowledge_base.py
graphite_api.py      graphite_api.py        graphite_api.py
agent.py (10 tools)  elasticsearch_api.py*  icinga_actions.py*
app.py               agent.py (17 tools)    agent.py (24 tools)
                                            app.py* (HITL + Action Mode)
                     
                     * = new or modified
```

| Metric | Phase 1 Core | Phase 1 Extended | Phase 2 |
|--------|-------------|-----------------|---------|
| Total tools | 10 | 17 | **24** |
| Read functions | 5 | 10 | 10 |
| ES functions | 0 | 5 | 5 |
| Action functions | 0 | 0 | **6** |
| Data sources | 3 (API, MySQL, Graphite) | 4 (+Elasticsearch) | 4 |
| Can modify Icinga? | ❌ No | ❌ No | ✅ **Yes** |
| Safety mechanisms | N/A | N/A | **HITL + Prompt + UI buttons** |

---

## 8. Complete Testing Guide

### 8.1 Prerequisites

```bash
# 1. Start the Icinga Docker container
docker compose up -d
# Wait 1-2 minutes for Icinga to fully initialize

# 2. Ensure Ollama is running with the Qwen model
ollama run qwen2.5-coder:7b
# (Ctrl+D to exit the REPL once it's pulled)

# 3. Install Python dependencies
python -m pip install -r requirements.txt
```

### 8.2 Module-by-Module Self-Tests

Each module has a built-in `if __name__ == "__main__":` test block. Run them independently:

```bash
# Test Icinga API connectivity (READ)
python icinga_api.py
# Expected: JSON output showing system status, hosts, check stats

# Test MySQL IDO connectivity (HISTORICAL)
python database_api.py
# Expected: Historical outages and downtimes from MySQL

# Test Elasticsearch (will show graceful fallback since ES_ENABLED=false)
python elasticsearch_api.py
# Expected: "ES is disabled" + fallback messages for each function

# Test Action module (will connect to Icinga API)
python icinga_actions.py
# Expected: Acknowledge, downtime, comment, recheck results
# (or connection errors if Icinga container isn't running)

# Test RAG knowledge base
python knowledge_base.py
# Expected: Troubleshooting guide results for "host is down"

# Test Graphite (demo mode)
python graphite_api.py
# Expected: 24 mock datapoints with CPU spike

# Test full agent initialization
python agent.py
# Expected: "24 tools registered" + a test query execution with full ReAct trace
```

### 8.3 Full Streamlit UI Test

```bash
python -m streamlit run app.py
```

**Test scenarios to try (READ — no action mode needed):**

| # | What to Type | What Should Happen |
|---|-------------|-------------------|
| 1 | "Show me the system status" | Agent calls `get_system_status()`, shows Icinga version and node info |
| 2 | "Are there any hosts that are DOWN?" | Agent calls `get_all_hosts(filter_state='DOWN')` |
| 3 | "List all services on icinga-master" | Agent calls `get_host_services('icinga-master')` |
| 4 | "What's the check latency?" | Agent calls `get_check_statistics()` |
| 5 | "Which hosts are in scheduled downtime?" | Agent calls `get_downtime_status()` |
| 6 | "Has icinga-master had any outages?" | Agent calls `get_historical_outages('icinga-master')` |
| 7 | "Search logs for 'disk full'" | Agent calls `search_elasticsearch_logs('disk full')` — shows ES fallback message |
| 8 | "Plot the CPU trend for icinga-master" | Agent calls `plot_historical_metrics()` — renders inline graph |

**Test scenarios (ACTION — enable Action Mode toggle in sidebar first):**

| # | What to Type | What Should Happen |
|---|-------------|-------------------|
| 9 | "Acknowledge the ping alert on icinga-master" | Agent DESCRIBES the action → asks "Shall I proceed?" → UI shows ✅/❌ buttons |
| 10 | "Schedule 2 hours of downtime on icinga-master" | Agent describes downtime window → asks for confirmation |
| 11 | "Force a re-check of icinga-master" | Agent confirms → executes → reports result |
| 12 | "Add a comment to icinga-master: testing AI agent" | Agent confirms → adds comment visible in Icinga Web 2 |

### 8.4 Verifying Actions in Icinga Web 2

After executing action commands, verify them in the Icinga Web 2 dashboard:

1. Open `http://localhost:80` in your browser
2. Login with `admin` / `admin123`
3. Navigate to the host/service you modified
4. You should see: acknowledgements, downtime schedules, comments, etc.

### 8.5 Watching the Agent Think (Terminal Output)

When you run Streamlit, the terminal shows the agent's internal thought process because `verbose=True`:

```
> Entering new AgentExecutor chain...
Thought: The user wants to know about critical alerts. I should use the 
get_critical_services tool to check.

Action: get_critical_services
Action Input: 

Observation: {'total_critical': 1, 'services': [{'host_name': 'icinga-master', 
'service_name': 'disk', 'state': 'CRITICAL', 'output': 'DISK CRITICAL...'}]}

Thought: I found 1 critical service. Let me search for troubleshooting steps.

Action: search_troubleshooting_guides
Action Input: disk space full critical

Observation: --- Section: Alert: Disk Space Full ---
1. Check Thresholds: Verify your warning/critical thresholds...

Thought: I now know the final answer.
Final Answer: There is 1 critical alert: The disk service on icinga-master is 
in CRITICAL state. The disk is running low on space...

> Finished chain.
```

This trace is invaluable for understanding HOW the agent reasons. Show this in your presentation!

---

## 9. Current Capabilities Summary Table

| Capability | Tools | Source Module | Data Source |
|-----------|-------|-------------|------------|
| System overview | `get_system_status` | `icinga_api.py` | Icinga API |
| Host listing and filtering | `get_all_hosts` | `icinga_api.py` | Icinga API |
| Host deep-dive | `get_host_details` | `icinga_api.py` | Icinga API |
| Critical alerts | `get_critical_services` | `icinga_api.py` | Icinga API |
| Template listing | `get_templates_and_zones` | `icinga_api.py` | Icinga API |
| Service deep-dive | `get_service_details` | `icinga_api.py` | Icinga API |
| Host service inventory | `get_host_services` | `icinga_api.py` | Icinga API |
| Notification audit | `get_notification_history` | `icinga_api.py` | Icinga API |
| Active downtime list | `get_downtime_status` | `icinga_api.py` | Icinga API |
| Monitoring health | `get_check_statistics` | `icinga_api.py` | Icinga API |
| Historical outages | `get_historical_outages` | `database_api.py` | MySQL IDO |
| Past downtimes | `get_recent_downtimes` | `database_api.py` | MySQL IDO |
| RCA troubleshooting | `search_troubleshooting_guides` | `knowledge_base.py` | ChromaDB (RAG) |
| Alert correlation | `group_and_summarize_alerts` | `agent.py` | Icinga API |
| Metric visualization | `plot_historical_metrics` | `graphite_api.py` | Graphite (demo) |
| Log search (ES) | `search_elasticsearch_logs` | `elasticsearch_api.py` | Elasticsearch |
| State timeline (ES) | `get_host_state_timeline` | `elasticsearch_api.py` | Elasticsearch |
| Acknowledge alerts | `acknowledge_alert` | `icinga_actions.py` | Icinga Actions API |
| Schedule downtime | `schedule_host_downtime` | `icinga_actions.py` | Icinga Actions API |
| Add comments | `add_host_comment` | `icinga_actions.py` | Icinga Actions API |
| Remove acknowledgement | `remove_alert_acknowledgement` | `icinga_actions.py` | Icinga Actions API |
| Send notifications | `send_notification` | `icinga_actions.py` | Icinga Actions API |
| Force re-check | `force_recheck` | `icinga_actions.py` | Icinga Actions API |

**Total: 24 tools across 6 modules talking to 5 data sources.**

---

## 10. What's Next — Future Roadmap

| Feature | Description | Status |
|---------|------------|--------|
| **VPN → Elasticsearch** | Connect to `opensearch.internal:9200`, set `ES_ENABLED=true` | Waiting for VPN |
| **SSH Auto-Remediation** | Use `paramiko` to restart crashed services remotely | `paramiko` added to requirements |
| **Icinga Director Integration** | Bulk-add hosts via the Director REST API | Planned |
| **Dedicated API Users** | Create `ai-read-user` and `ai-action-user` with scoped permissions | Planned |
| **Persistent Chat Memory** | LangChain memory buffer so the agent remembers earlier questions | Planned |
| **Multi-Agent Architecture** | Separate read agent and action agent that collaborate | Planned |

---

> **Final Note:** This project demonstrates production-grade patterns (RAG, ReAct agents, HITL safety, feature flags, strategy patterns, graceful degradation) that are used at companies like Google, Netflix, and Datadog. The same architecture — LLM + Tools + External APIs — is the foundation of every AI agent being built in the industry today.
