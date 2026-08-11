# Phase 2 Technical Deep Dive: OpenSearch Integration & Core Action Features

> This document explains everything that was built, why it was built that way, and how to test every feature. It is designed for learning and onboarding.

---

## Table of Contents
1. [Why We Built This](#why-we-built-this)
2. [Architecture: The Full Stack](#architecture-the-full-stack)
3. [Part 1: Isolated OpenSearch Integration](#part-1-isolated-opensearch-integration)
4. [Part 2: Core Action Features](#part-2-core-action-features)
5. [The Icinga ↔ OpenSearch Dependency Proof](#the-icinga--opensearch-dependency-proof)
6. [Testing Guide](#testing-guide)
7. [FAQ & Troubleshooting](#faq--troubleshooting)

---

## Why We Built This

### Problem 1: Unverified OpenSearch Integration
The original `elasticsearch_api.py` was built to connect to the company's production OpenSearch server at `opensearch.internal`. However:
- That server contained real company data — connecting a test agent to it was risky.
- There was no way to prove the **dependency** between Icinga (the monitoring tool) and OpenSearch (the log database) because they were running independently on separate systems.

### Problem 2: Missing Core Action Capabilities
The agent could **observe** the monitoring system, but an AIOps product must also be able to **act**. The most critical missing features were:
- **Host Onboarding**: The ability to register a brand new server into monitoring with a single command.
- **Template Creation**: The ability to create reusable monitoring blueprints.

---

## Architecture: The Full Stack

After this implementation, the complete local lab looks like this:

```
┌─────────────────────────────────────────────────────┐
│                 Docker Network: icinga-net           │
│                                                     │
│  ┌──────────────────┐      ┌───────────────────┐   │
│  │  icinga-lab      │─────▶│  opensearch-lab   │   │
│  │ (jordan/icinga2) │      │ (OpenSearch 2.13) │   │
│  │                  │      │                   │   │
│  │  - Icinga 2      │      │  - Empty sandbox  │   │
│  │  - MariaDB IDO   │      │  - No auth (dev)  │   │
│  │  - Icinga Web 2  │      │  - Port 9200      │   │
│  │  - Director API  │      │                   │   │
│  │  - ES Writer ────┼─────▶│  Receives all     │   │
│  │                  │      │  Icinga metrics   │   │
│  └──────────────────┘      └───────────────────┘   │
│         │                          │                │
└─────────┼──────────────────────────┼────────────────┘
          │                          │
          ▼                          ▼
   Your Python Agent reads from BOTH via localhost:5665 / localhost:9200
```

### Key Design Decision: Shared Docker Network
We put both containers on the same Docker network (`icinga-net`). This allows:
- Icinga (inside Docker) to send data to `opensearch:9200` (using the container hostname).
- Your Python agent (on your laptop) to connect to `localhost:9200` (via port mapping).

This is what **proves the dependency** — Icinga is the **data producer** and OpenSearch is the **data consumer**.

---

## Part 1: Isolated OpenSearch Integration

### What Changed

#### `docker-compose.yaml`
We added a second service:
```yaml
opensearch:
  image: opensearchproject/opensearch:2.13.0
  environment:
    - discovery.type=single-node
    - DISABLE_SECURITY_PLUGIN=true   # No auth for local dev
```
Key flags:
- `discovery.type=single-node` — No cluster needed, just one node for testing.
- `DISABLE_SECURITY_PLUGIN=true` — Removes authentication requirement for easy local access.
- `OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m` — Limits memory to 512MB so it doesn't eat your laptop RAM.

#### Configuring Icinga to Write to OpenSearch
Icinga 2 has a built-in feature called the **Elasticsearch Writer** (`ElasticsearchWriter`). When enabled, it automatically forwards every check result, state change, and performance data point to an OpenSearch/Elasticsearch endpoint.

We configure it by running inside the container:
```bash
# Enable the feature
icinga2 feature enable elasticsearch

# Configure it to point to our sandbox
cat > /etc/icinga2/features-available/elasticsearch.conf << EOF
object ElasticsearchWriter "elasticsearch" {
  host = "opensearch"        # Docker hostname of our OpenSearch container
  port = 9200
  index = "icinga2"          # Creates indices: icinga2-YYYY.MM.DD
  enable_send_perfdata = true
}
EOF

service icinga2 restart
```

After this, Icinga writes data to OpenSearch automatically. The agent then reads this data.

#### `elasticsearch_api.py`
Updated two critical settings:
```python
# Before (company server — DO NOT USE)
ES_HOST = "opensearch.internal"
ES_INDEX_PATTERN = "t9-*"

# After (local sandbox)
ES_HOST = "localhost"
ES_INDEX_PATTERN = "icinga2-*"
```

---

## Part 2: Core Action Features

### How the Icinga v1 Objects API Works for Host Management

We use the **Icinga 2 v1 Objects API** (not Icinga Director) for host onboarding and management. Here is why this is the better choice:

| Feature | Icinga Director API | Icinga v1 Objects API (What We Use) |
|---|---|---|
| Host goes live | Requires explicit "deploy" step | **Immediately — no deploy needed** |
| API stability | Varies by image version | **Stable and battle-tested** |
| Container support | Partial (PHP errors in jordan/icinga2) | **Full support** |
| Authentication | Separate web credentials | **Same as monitoring API** |

```
Core Icinga 2 API: https://localhost:5665/v1/...
  - GET /objects/hosts          → List all hosts
  - PUT /objects/hosts/{name}   → Create a new host (LIVE IMMEDIATELY)
  - DELETE /objects/hosts/{name}→ Remove a host
  - GET /objects/checkcommands  → List available check plugins (our "templates")
```

### The Onboarding Workflow (Step by Step)

When you ask the agent to onboard a new host, it follows this exact workflow:

```
User: "Onboard web-prod-01 at 192.168.1.100 using linux-server template"
         │
         ▼
Step 1: list_director_templates()
         └── Check if 'linux-server' template exists
         │
         ▼ (if not exists)
Step 2: create_host_template('linux-server', 'hostalive')
         └── POST to /icingaweb2/director/hosttemplate
         └── Creates a reusable blueprint
         │
         ▼
Step 3: onboard_new_host('web-prod-01', '192.168.1.100', 'linux-server')
         └── POST to /icingaweb2/director/host
         └── Host is now "staged" — not yet active
         │
         ▼
Step 4: deploy_director_config()
         └── POST to /icingaweb2/director/config/deploy
         └── Icinga compiles the new config
         └── Host is NOW LIVE — monitoring starts immediately
         │
         ▼
Step 5: force_recheck('web-prod-01')   [optional]
         └── Immediately runs a ping check to verify host is reachable
```

### New Functions Added to `icinga_actions.py`

| Function | API Endpoint | Description |
|---|---|---|
| `create_host_template()` | `POST /director/hosttemplate` | Create a reusable monitoring blueprint |
| `create_host()` | `POST /director/host` | Onboard a new host using a template |
| `deploy_director_config()` | `POST /director/config/deploy` | Push staged config to live Icinga |
| `list_director_hosts()` | `GET /director/hosts` | List all managed hosts |
| `list_director_templates()` | `GET /director/hosttemplates` | List all templates |

### New Tools Added to `agent.py`

| Tool Name | Wraps | Mode |
|---|---|---|
| `create_host_template` | `icinga_actions.create_host_template()` | ⚠️ ACTION |
| `onboard_new_host` | `icinga_actions.create_host()` | ⚠️ ACTION |
| `deploy_director_config` | `icinga_actions.deploy_director_config()` | ⚠️ ACTION |
| `list_director_hosts` | `icinga_actions.list_director_hosts()` | 📖 READ |
| `list_director_templates` | `icinga_actions.list_director_templates()` | 📖 READ |

### System Prompt Update
The agent's system prompt was updated to include:
1. **Awareness** of the new tools.
2. A **strict onboarding workflow** so the agent always follows the correct order.
3. **HITL confirmation** is required before any Director write operation.

---

## The Icinga ↔ OpenSearch Dependency Proof

This is the core thing we wanted to demonstrate.

### How it works in 3 steps:

1. **Icinga monitors** — It runs checks every minute on all hosts (ping, SSH, disk, etc.).

2. **Icinga writes to OpenSearch** — The `ElasticsearchWriter` feature automatically sends every check result to OpenSearch in real-time. A check result looks like this in OpenSearch:
```json
{
  "@timestamp": "2026-08-07T12:00:00Z",
  "host": { "name": "icinga-master" },
  "service": { "name": "disk /" },
  "state": 0,
  "output": "DISK OK - free space: / 15234 MB (78% inode=99%):",
  "check_result": { "performance_data": ["disk=15234MB;..."] }
}
```

3. **Your Agent reads from OpenSearch** — When you ask the agent "Show me the alert history for the last 7 days", it queries OpenSearch (not Icinga) for this historical data.

### This proves two things:
- **Data Dependency**: OpenSearch data comes directly FROM Icinga. If Icinga goes down, no new data is written to OpenSearch.
- **Functional Dependency**: Your agent's historical analysis features (log searches, anomaly detection, state timelines) DEPEND on OpenSearch being populated by Icinga.

---

## Testing Guide

### Step 1: Verify Containers Are Running
```bash
docker ps
# You should see BOTH containers:
# icinga-lab     (ports: 80, 443, 5665, 3306)
# opensearch-lab (ports: 9200, 9600)
```

### Step 2: Verify OpenSearch is Healthy
```bash
# Check cluster health
curl http://localhost:9200/_cluster/health

# Expected output:
# {"status":"green","number_of_nodes":1,...}
```

### Step 3: Configure Icinga to Write to OpenSearch (ONE-TIME SETUP)
> **You need to do this step manually after the containers start.**

Run these commands in your terminal:
```bash
# 1. Enable the elasticsearch writer feature inside the Icinga container
docker exec icinga-lab icinga2 feature enable elasticsearch

# 2. Configure the elasticsearch writer to point to our local opensearch
docker exec icinga-lab bash -c "cat > /etc/icinga2/features-available/elasticsearch.conf << 'EOF'
object ElasticsearchWriter \"elasticsearch\" {
  host = \"opensearch\"
  port = 9200
  index = \"icinga2\"
  enable_send_perfdata = true
  flush_threshold = 1024
  flush_interval = 10
}
EOF"

# 3. Restart Icinga to apply the config
docker exec icinga-lab service icinga2 restart

# 4. Wait 2 minutes, then verify data is flowing into OpenSearch
curl http://localhost:9200/icinga2-*/_count
# Expected: {"count": <some number > 0>,...}
```

### Step 4: Test the Agent — Read Features
Start the Streamlit app and try these prompts:

| Prompt | Expected Tool | Expected Result |
|---|---|---|
| "Show me system status" | `get_system_status` | Icinga version and uptime |
| "Are there any hosts down?" | `get_all_hosts` | List of UP/DOWN hosts |
| "Search logs for 'disk'" | `search_elasticsearch_logs` | Events from OpenSearch |
| "Check Elasticsearch health" | `get_elasticsearch_cluster_health` | `{"status": "green"}` |
| "What indices exist in OpenSearch?" | `get_elasticsearch_indices` | List of `icinga2-*` indices |

### Step 5: Test the Agent — Action Mode
**Enable Action Mode** in the sidebar toggle, then try these prompts:

#### Test Alert Actions:
```
"Acknowledge the problem on icinga-master"
"Schedule 2 hours of downtime for icinga-master starting now"
"Add a comment to icinga-master: Testing AI Agent actions"
"Force a re-check of icinga-master"
```

#### Test Host Onboarding:
```
Step 1: "What host templates are available?"
         → Agent calls list_director_templates()

Step 2: "Create a new host template called linux-server with hostalive check"
         → Agent describes the action, asks for confirmation
         → You click "Yes, proceed"
         → Agent creates the template

Step 3: "Onboard a new host called test-server-01 with IP 192.168.100.10 using linux-server template"
         → Agent describes: hostname, IP, template
         → You click "Yes, proceed"
         → Agent creates the host

Step 4: "Deploy the configuration"
         → Agent deploys, new host goes live

Step 5: "Show me all hosts in Icinga" or visit http://localhost/icingaweb2
         → test-server-01 should appear and start being monitored
```

### Step 6: Verify the Dependency (Smoking Gun Test)
```bash
# 1. Check how many docs are in OpenSearch BEFORE stopping Icinga
curl http://localhost:9200/icinga2-*/_count

# 2. Stop Icinga inside the container
docker exec icinga-lab service icinga2 stop

# 3. Wait 2 minutes, then check again
curl http://localhost:9200/icinga2-*/_count
# Count should NOT be increasing anymore — proving Icinga is the data producer!

# 4. Restart Icinga
docker exec icinga-lab service icinga2 start

# 5. After 2 minutes, count should grow again
curl http://localhost:9200/icinga2-*/_count
```

---

## FAQ & Troubleshooting

### Q: The agent says "OpenSearch not connected"
**A:** Check that `opensearch-lab` container is running and healthy:
```bash
docker ps | grep opensearch
curl http://localhost:9200/
```

### Q: icinga2-* indices don't exist in OpenSearch
**A:** The `ElasticsearchWriter` hasn't been configured yet. Follow **Step 3** in the Testing Guide.

### Q: Icinga API returns 401 Unauthorized
**A:** The API password is regenerated when Docker volumes are wiped. Fix it by running:
```bash
# Get the new password
docker exec icinga-lab cat /etc/icinga2/conf.d/api-users.conf

# Update icinga_api.py and icinga_actions.py with the new password
```

### Q: Director API returns 404 for /director/hosttemplate
**A:** Icinga Director module may not be fully loaded. Try accessing `http://localhost/icingaweb2` in your browser first and log in as `admin/admin123`. This initializes the Director module.

### Q: Host is created but not appearing in Icinga Web
**A:** You must call `deploy_director_config()` after creating the host. Director keeps changes "staged" until explicitly deployed.

### Q: OpenSearch says "max virtual memory areas vm.max_map_count [65530] is too low"
**A:** This is a Linux kernel limitation. On Windows/WSL, it's handled automatically by Docker Desktop.
