# Icinga AI Agent — Technical Documentation

## Overview

The Icinga AI Agent is an **AIOps (AI for IT Operations)** product that wraps Icinga 2 — a production-grade monitoring platform — with a conversational AI interface. Instead of clicking through dashboards or writing API payloads manually, operators interact with the system using plain English.

---

## 1. Architecture: How It All Fits Together

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER (Chat UI)                           │
│                      http://localhost:8501                        │
└─────────────────────────┬────────────────────────────────────────┘
                          │ Natural Language
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     app.py  (Streamlit UI)                       │
│          Renders chat, history, mode toggle, plots               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    agent.py  (LangChain Agent)                   │
│   • LLM: Qwen 2.5 Coder 7B (via Ollama, runs 100% locally)      │
│   • Framework: LangChain ReAct Agent                             │
│   • Decides WHICH tool(s) to call based on the user intent       │
│   • Enforces Human-in-the-Loop for all write operations          │
└────┬───────────────────┬─────────────────────┬───────────────────┘
     │                   │                     │
     ▼                   ▼                     ▼
┌──────────┐    ┌──────────────────┐   ┌──────────────────────────┐
│icinga_api│    │icinga_actions.py │   │elasticsearch_api.py      │
│ .py      │    │                  │   │                          │
│ READ ops │    │ WRITE ops        │   │ Log Search & Analytics   │
│          │    │ - Alert Mgmt     │   │ (OpenSearch)             │
│ GET host │    │ - Director API   │   │                          │
│ services │    │                  │   │ Indexes: icinga2-*       │
│ alerts   │    │                  │   └──────────────────────────┘
└────┬─────┘    └───────┬──────────┘
     │                  │
     ▼                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Docker Network: icinga-net                     │
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────┐   ┌───────────────┐  │
│  │  icinga-lab     │   │  opensearch-lab │   │ dashboards    │  │
│  │  Port 5665 API  │   │  Port 9200      │   │ Port 5601     │  │
│  │  Port 80 Web    │   │  Stores events  │   │ Kibana-like   │  │
│  │  Icinga 2 Core  │   │  + perf data    │   │ visual UI     │  │
│  └─────────────────┘   └─────────────────┘   └───────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. The LLM — How the Agent "Thinks"

The agent uses **Qwen 2.5 Coder 7B**, running locally via Ollama. It uses the **ReAct (Reasoning + Acting)** pattern:

```
User: "Create a host called db-01"

Thought: The user wants to create a host. I need the IP address first.
         This is a required field — I must ask.

Final Answer: "I can create host 'db-01' for you! I need one required piece of
              information before I proceed:
              • IP Address: What is the IP address or DNS name for db-01?
              Once you provide that, I'll also tell you the defaults I plan to use
              (check command: hostalive, template: generic-host) for your approval."
```

This ReAct loop repeats (Thought → Action → Observation) up to **7 times** per query, allowing the agent to handle multi-step workflows like create template → create host → deploy — all in a single conversation turn.

---

## 3. All Action Features

### Alert Management Actions (Icinga 2 Core API — `https://localhost:5665/v1`)

These write directly to the live Icinga 2 engine in real-time. No deploy step needed.

| Feature | What It Does | Status |
|---|---|---|
| **Acknowledge Problem** | Stops repeated alert notifications for a known issue | ✅ Working |
| **Schedule Downtime** | Mutes all alerts during planned maintenance + child services | ✅ Working |
| **Add Comment** | Adds a sticky note visible in Icinga Web dashboard | ✅ Working |
| **Remove Acknowledgement** | Re-enables notifications after a premature ack | ✅ Working |
| **Send Custom Notification** | Force-sends notification to on-call team | ✅ Working |
| **Force Re-check** | Immediately triggers a health check without waiting | ✅ Working |

### Configuration Management Actions (Director API — `http://localhost/icingaweb2/director`)

These write to Icinga Director staging. A **deploy step is always required** at the end.

| Feature | Required Fields | Optional Fields (Defaults) | Status |
|---|---|---|---|
| **Create Host Group** | `object_name` | `display_name` | ✅ Working |
| **Create Host Template** | `object_name` | `check_command` → `hostalive` | ✅ Working |
| **Onboard New Host** | `object_name`, `address`, `imports` | `display_name`, `groups` | ✅ Working |
| **Create Service Group** | `object_name` | `display_name` | ✅ Working |
| **Create Service Template** | `object_name`, `check_command` | — | ✅ Working |
| **Create Service** | `object_name`, `host`, `imports` | — | ✅ Working |
| **Create Service Set** | `object_name`, `host` | `description` | ✅ Working |
| **Create Check Command** | `object_name`, `command` | type → `PluginCheck` | ✅ Working |
| **Deploy Config** | — | — | ✅ Working |
| **List Hosts** | — | `filter_name` | ✅ Working |
| **List Templates** | — | — | ✅ Working |

---

## 4. End-to-End Workflow Example: Onboarding a New Host

```
1. User: "Add a new Linux server called app-prod-02 at 10.0.1.55"

2. Agent Thought: I have hostname + address. I'll check existing templates first.

3. Agent calls: list_director_templates()
   Result: {"templates": []}  ← No templates exist yet

4. Agent responds: "I'll create template 'generic-linux' (hostalive check) then
                   onboard 'app-prod-02' at 10.0.1.55. Shall I proceed?"

5. User: "Yes, proceed"

6. Agent calls: create_host_template('generic-linux', 'hostalive')
7. Agent calls: create_host('app-prod-02', '10.0.1.55', ['generic-linux'])
8. Agent calls: deploy_director_config()

9. Agent: "✅ Done! 'app-prod-02' is now live in Icinga monitoring."
```

---

## 5. OpenSearch Integration — How Logs Flow

```
Icinga 2 Engine
      │  (every state change, check result, perf data)
      ▼
ElasticsearchWriter Feature (inside icinga-lab container)
      │  Writes to → opensearch-lab:9200
      │  Index: icinga2-YYYY.MM.DD
      ▼
OpenSearch (localhost:9200)
      ├── AI Agent: log search, spike detection, anomaly aggregation
      └── OpenSearch Dashboards (localhost:5601): human visual verification
```

**AI Agent log capabilities:**
- Search logs by keyword across all time
- Detect log volume spikes (last 1h vs 24h average)
- Aggregate top failing hosts
- Reconstruct a host's UP/DOWN timeline over 30 days
- Custom Lucene queries (e.g., `status:CRITICAL AND host:*db*`)

---

## 6. Human-in-the-Loop Safety Model

```
User Request
     │
     ├── READ operation? → Execute immediately, no confirmation needed
     │
     └── WRITE operation?
              │
              ├── Missing REQUIRED fields? → STOP, ask the user
              │
              └── All required fields present?
                       │
                       └── State defaults for optional fields
                           → Ask for EXPLICIT APPROVAL
                                    │
                                    ├── User says "yes" → Execute action
                                    └── User says "no"  → Cancel, do nothing
```

---

## 7. How to Make It Smarter — Improvement Roadmap

### Tier 1: Near-Term (High Impact, Low Effort)

| Improvement | Why It Matters | How to Implement |
|---|---|---|
| **Conversation Memory** | Each message is currently isolated — the agent forgets previous turns | Add `ConversationBufferMemory` to LangChain agent |
| **Upgrade the LLM** | Qwen 7B occasionally misuses tool arguments | Switch to `qwen2.5:14b` or `llama3.1:8b` via Ollama |
| **Input Validation** | Director API accepts silently bad configs | Add Pydantic models to validate all inputs before calling `_director_request()` |
| **Richer Check Command Catalog** | Agent only knows 10 check types | Add a dynamic `list_check_plugins()` tool that reads all available Nagios plugins |

### Tier 2: Mid-Term (Feature Expansions)

| Improvement | Why It Matters | How to Implement |
|---|---|---|
| **Topology Awareness** | Agent doesn't know parent-child host relationships — a parent DOWN explains 50 UNREACHABLE children | Build a dependency graph from `get_host_details()` parent vars |
| **Anomaly Detection** | Agent is reactive, only sees issues after they happen | Add z-score or Prophet forecasting over OpenSearch perf data |
| **Notification Management** | Can't manage WHO gets notified and when | Add Director API tools for `/user`, `/usergroup`, `/notification` |
| **Bulk Onboarding** | Onboarding 50 hosts one-by-one is tedious | Add `bulk_onboard_hosts(csv_data)` tool that batches Director calls |

### Tier 3: Long-Term (Architecture Upgrades)

| Improvement | Why It Matters | How to Implement |
|---|---|---|
| **Multi-Agent Architecture** | Single agent handles everything, long reasoning chains cause errors | Supervisor + specialized sub-agents: ReadAgent, WriteAgent, AnalyticsAgent |
| **RAG over Documentation** | Agent gives generic answers — should use your internal runbooks | Load docs into ChromaDB, use RAG to ground answers in real org knowledge |
| **Automated Remediation** | Agent identifies root cause but can't fix it | Safe auto-remediation playbooks (disk full → delete logs, crash → restart) |
| **Predictive Alerting** | Alert BEFORE things break, not after | Train forecasting model on OpenSearch perf data to predict threshold breaches |
| **MCP Server** | Productize for enterprise sales | Wrap `icinga_actions.py` in an MCP Server so any AI tool (Claude, Copilot) can natively use Icinga actions |

---

## 8. File Map

```
Icinga_AI_Agent/
├── app.py                  # Streamlit UI — chat interface
├── agent.py                # LangChain Agent — tool registry + prompt + LLM
├── icinga_api.py           # READ operations (Icinga 2 Core API)
├── icinga_actions.py       # WRITE operations (Icinga Core + Director API)
├── elasticsearch_api.py    # OpenSearch log analytics
├── knowledge_base.py       # Internal troubleshooting guide search
├── database_api.py         # Historical outage/downtime DB queries
├── graphite_api.py         # Graphite time-series metric queries
├── verify_integration.py   # Quick sanity check for all connections
├── AGENT_DOCUMENTATION.md  # ← This file
└── docker-compose.yaml     # Spins up: icinga, opensearch, dashboards
```
