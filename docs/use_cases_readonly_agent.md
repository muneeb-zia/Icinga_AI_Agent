# Use Cases: Read-Only Observability Agent (Phase 1)

The Read-Only Observability Agent acts as an intelligent assistant that can see everything in your infrastructure but cannot modify it. Its superpower is data aggregation, natural language processing, and correlation.

## 1. Natural Language Dashboarding
Instead of clicking through complex Icinga Web 2 interfaces to build a custom view, users can simply ask for the data they need.
- **Prompt:** *"Show me all Windows servers in the DMZ zone that are currently DOWN."*
- **Execution:** The agent queries the Icinga REST API (`/v1/objects/hosts`), filters by OS and Zone, and formats the output into a clean table.

## 2. Root Cause Analysis (RCA) via Contextual RAG
When an alert fires, the agent doesn't just pass along the error message; it acts as a Level 1 Support Engineer by reading documentation.
- **Prompt:** *"The Postgres service on db-master is CRITICAL. What should I do?"*
- **Execution:** The agent reads the live API error, searches the internal Knowledge Base (RAG pipeline) for "Postgres CRITICAL", and replies with the exact troubleshooting steps from your company's playbook.

## 3. Alert Correlation and Noise Reduction
Icinga can cause alert fatigue. If a core switch goes down, 50 servers behind it might also alert as DOWN. 
- **Prompt:** *"Why is my phone blowing up with alerts? Give me a summary of what's wrong."*
- **Execution:** The agent pulls all 50 critical alerts, analyzes the parent/child topology or tags, and summarizes: *"Core Switch A is offline, causing 50 downstream alerts. Focus on fixing Switch A. The rest are false positives."*

## 4. Historical Trend Analysis (Graphite Integration)
The agent leverages Time-Series data to answer questions about performance trends leading up to an event.
- **Prompt:** *"The web server crashed 10 minutes ago. What did the CPU and Memory look like right before that?"*
- **Execution:** The agent queries the Graphite Render API for the last 1 hour of CPU/Memory data, identifies the massive spike at the 45-minute mark, and presents a summary (or a drawn graph).

## 5. Shift Handover Reports
Perfect for NOC (Network Operations Center) teams transitioning between day and night shifts.
- **Prompt:** *"Generate a shift handover report for the last 12 hours."*
- **Execution:** The agent queries the MySQL database for all outages in the last 12 hours, queries the API for currently unacknowledged criticals, and drafts a professional email/summary of the system's state for the next engineer.
