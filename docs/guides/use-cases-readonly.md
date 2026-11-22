# Use Cases: Read-Only Observability Agent (Phase 1)

The Read-Only Observability Agent acts as an intelligent assistant that can see everything in your infrastructure but cannot modify it. Its superpower is data aggregation, natural language processing, and correlation.

---

## Core Use Cases (1–5)

### 1. Natural Language Dashboarding
Instead of clicking through complex Icinga Web 2 interfaces to build a custom view, users can simply ask for the data they need.
- **Prompt:** *"Show me all Windows servers in the DMZ zone that are currently DOWN."*
- **Execution:** The agent queries the Icinga REST API (`/v1/objects/hosts`), filters by OS and Zone, and formats the output into a clean table.
- **Tool:** `get_all_hosts(filter_state='DOWN')`

### 2. Root Cause Analysis (RCA) via Contextual RAG
When an alert fires, the agent doesn't just pass along the error message; it acts as a Level 1 Support Engineer by reading documentation.
- **Prompt:** *"The Postgres service on db-master is CRITICAL. What should I do?"*
- **Execution:** The agent reads the live API error, searches the internal Knowledge Base (RAG pipeline) for "Postgres CRITICAL", and replies with the exact troubleshooting steps from your company's playbook.
- **Tool:** `search_troubleshooting_guides(query)`

### 3. Alert Correlation and Noise Reduction
Icinga can cause alert fatigue. If a core switch goes down, 50 servers behind it might also alert as DOWN. 
- **Prompt:** *"Why is my phone blowing up with alerts? Give me a summary of what's wrong."*
- **Execution:** The agent pulls all critical alerts, analyzes the parent/child topology or tags, and summarizes: *"Core Switch A is offline, causing 50 downstream alerts. Focus on fixing Switch A."*
- **Tool:** `group_and_summarize_alerts()`

### 4. Historical Trend Analysis (Graphite Integration)
The agent leverages Time-Series data to answer questions about performance trends leading up to an event.
- **Prompt:** *"The web server crashed 10 minutes ago. What did the CPU and Memory look like right before that?"*
- **Execution:** The agent queries the Graphite Render API for the last 1 hour of CPU/Memory data, identifies the massive spike at the 45-minute mark, and presents a summary (or a drawn graph).
- **Tool:** `plot_historical_metrics(hostname, metric_name)`

### 5. Shift Handover Reports
Perfect for NOC (Network Operations Center) teams transitioning between day and night shifts.
- **Prompt:** *"Generate a shift handover report for the last 12 hours."*
- **Execution:** The agent queries the MySQL database for all outages in the last 12 hours, queries the API for currently unacknowledged criticals, and drafts a professional summary of the system's state for the next engineer.
- **Tools:** `get_historical_outages(hostname)`, `get_recent_downtimes()`, `get_critical_services()`

---

## Extended Use Cases (6–10)

### 6. Service-Level Deep Dive
Drill into the detailed status and configuration of a specific service on a specific host — state, output, performance data, check intervals, acknowledgement status, and more.
- **Prompt:** *"What is the status of the SSH service on db-master?"*
- **Execution:** The agent queries the Icinga API for the specific service object (`/v1/objects/services/{host}!{service}`), returning state, output, check timing, performance data, and whether it's acknowledged or in downtime.
- **Tool:** `get_service_details(hostname, service_name)`
- **API Endpoint:** `GET /v1/objects/services/{host}!{service}`

### 7. Host Service Inventory
Get a complete inventory of every service being monitored on a host, with current states and a summary breakdown.
- **Prompt:** *"List all services being monitored on web-01."*
- **Execution:** The agent queries all services filtered by hostname, returns each service's name, state, output, and check command, plus a state summary (e.g., 8 OK, 1 WARNING, 1 CRITICAL).
- **Tool:** `get_host_services(hostname)`
- **API Endpoint:** `GET /v1/objects/services` with host filter

### 8. Notification Audit Trail
View recent notification configurations — who gets notified, via which command, and when the last notification was sent.
- **Prompt:** *"Who was notified about the last critical alert?"*
- **Prompt:** *"Show me the notification history for web-01."*
- **Execution:** The agent queries the notifications objects endpoint, optionally filtered by hostname, and returns the notification command, users, user groups, last/next notification timestamps, and notification types.
- **Tool:** `get_notification_history(hostname=None)`
- **API Endpoint:** `GET /v1/objects/notifications`

### 9. Active Downtime Inspector
List all hosts and services that are currently in an active scheduled downtime — useful for understanding what's intentionally muted.
- **Prompt:** *"Which hosts are currently in scheduled downtime?"*
- **Prompt:** *"Is anything muted right now?"*
- **Execution:** The agent queries both hosts and services with `downtime_depth > 0`, returning a combined view of everything currently in downtime with state and address information.
- **Tool:** `get_downtime_status()`
- **API Endpoint:** `GET /v1/objects/hosts` and `GET /v1/objects/services` filtered by `downtime_depth > 0`

### 10. Monitoring Health Check
Check the health of the Icinga monitoring system itself — check latency, execution time, active/passive check counts, host/service state totals, and uptime.
- **Prompt:** *"Is our Icinga system itself healthy? What's the check latency?"*
- **Prompt:** *"How many active checks are running?"*
- **Execution:** The agent queries the CIB (Common Information Base) status endpoint for operational performance statistics, returning latency (min/max/avg), execution times, check counts, and overall state summaries.
- **Tool:** `get_check_statistics()`
- **API Endpoint:** `GET /v1/status/CIB`

---

## Elasticsearch-Powered Use Cases (Ready for opensearch.internal:9200)

These use cases require VPN access to the production Elasticsearch instance. When `ES_ENABLED=false` (default), they return a graceful fallback message directing users to the MySQL IDO data.

### 11. Deep Log Search
Free-text search across all Icinga log indices in Elasticsearch for specific error messages, patterns, or events.
- **Prompt:** *"Search the logs for 'disk full' in the last 7 days."*
- **Prompt:** *"Find all occurrences of 'connection refused' in the past 24 hours."*
- **Tool:** `search_elasticsearch_logs(keyword, time_range)`

### 12. Host State Timeline
Build an UP/DOWN state change timeline for a host over a given period — useful for identifying recurring outage patterns and understanding availability.
- **Prompt:** *"Show me the state timeline for db-master over the last 30 days."*
- **Prompt:** *"Has web-01 had any recurring downtime patterns?"*
- **Tool:** `get_host_state_timeline(hostname, time_range)`
