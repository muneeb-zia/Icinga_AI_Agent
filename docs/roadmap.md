# Icinga AI Agent Development Roadmap

## 1. Project Overview & Architecture
**Objective:** Build an intelligent, context-aware AI agent integrated with Icinga 2. 
**Environment:** Dockerized Icinga 2 instance.
**Deployment Target:** Antigravityy (Agentic Framework/Workspace).
**Phases:** 
- **Phase 1:** Read-Only Observability Agent (Querying, Filtering, Summarizing).
- **Phase 2:** Action-Capable Management Agent (Onboarding, Bulk Operations, Config Management).

---

## 2. Phase 1: Read-Only Observability Agent (Current Focus)
The agent must act as a natural language interface for the Icinga 2 API, retrieving and formatting dashboard data, host states, and critical alerts.

### 2.1. Required Agent Tools (Functions to Implement)
The agent needs access to the following programmatic tools (Python/REST API):
- `get_system_status()`: Queries `/v1/status` to get a high-level dashboard overview (total hosts, active checks).
- `get_all_hosts(filter_state=None)`: Queries `/v1/objects/hosts`. Can filter by UP, DOWN, or UNREACHABLE.
- `get_host_details(hostname)`: Retrieves specific template usage, custom variables, and performance data for a single host.
- `get_critical_services()`: Queries `/v1/objects/services` with `filter=service.state==2` to instantly pull active critical alerts.
- `get_templates_and_zones()`: Queries `/v1/objects/hosttemplates` to list available configurations.

### 2.2. Execution Steps for Phase 1
1. **API Authentication Setup:** Generate Icinga 2 API credentials (API user configured in `conf.d/api-users.conf`).
2. **Tool Binding:** Wrap the REST API calls into distinct Python functions with strict docstrings so the LLM understands when to call them.
3. **Data Parsing:** Icinga's JSON responses are deeply nested. Strip out unnecessary metadata before feeding it to the LLM to save token context and prevent hallucinations.

---

## 3. Phase 2: Action-Capable Management Agent (Future Scope)
Transitioning from `GET` requests to `POST`/`PUT` requests.
- `create_single_host(hostname, template, address)`: POST to `/v1/objects/hosts/hostname`.
- `bulk_onboard_hosts(csv_or_json_data)`: Iterative POST requests or leveraging Icinga Director API for bulk imports.
- `acknowledge_problem(host, service, comment)`: POST to `/v1/actions/acknowledge-problem`.

---

## 4. The "Extra Mile": Making the Agent *Very Smart*
To exceed standard internship expectations and build a truly advanced agent, implement the following two features:

### Extra Step 1: Root Cause Analysis (RCA) via Contextual RAG
Instead of just reporting "Host XYZ is DOWN," the agent should cross-reference the failure with historical logs or Icinga documentation. 
- **How:** Implement a Retrieval-Augmented Generation (RAG) pipeline. Index your company's internal troubleshooting guides or past resolved tickets. When `get_critical_services()` returns an error, the agent automatically runs a similarity search to suggest the most likely fix.

### Extra Step 2: Correlated Alert Summarization
Icinga can generate alert fatigue if a core switch goes down, triggering 50 dependent host alerts.
- **How:** Give the agent a `group_and_summarize_alerts()` tool. Prompt the agent to analyze the network topology (parent/child relationships in Icinga) and output a single, smart summary: *"Switch A is down, causing 50 downstream hosts to appear offline. Focus on Switch A."*