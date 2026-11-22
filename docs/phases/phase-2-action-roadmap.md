# Phase 2: Action-Capable Agent Roadmap

This roadmap outlines the technical steps required to transition the Icinga AI Agent from a "Read-Only Observability" tool into an active "AIOps Management" assistant capable of executing changes and auto-remediating issues.

## 1. Security & Authentication Overhaul
Before giving the AI the power to change infrastructure, we must ensure it is done securely.
* **API User Permissions:** Create a dedicated `ai-action-user` in Icinga's `api-users.conf` with explicit write permissions (e.g., `actions/*`, `objects/modify/*`). We will *not* use the root user for actions.
* **Human-in-the-Loop (HITL):** Implement a safety mechanism in `app.py` (Streamlit). If the LLM decides to execute a destructive or major command (like rebooting a server), it must pause and render a "Confirm Action" button in the UI for the user to click before proceeding.

## 2. Implementing POST/PUT Actions (`icinga_api.py`)
We will expand the API module to include functions that write data to Icinga.
* **`acknowledge_alert(hostname, service, comment)`:** Sends a POST request to `/v1/actions/acknowledge-problem`. This stops Icinga from sending further email/SMS alerts.
* **`schedule_downtime(hostname, start_time, end_time, comment)`:** Calculates epoch timestamps and sends a POST to `/v1/actions/schedule-downtime`.
* **`add_comment(hostname, service, comment)`:** Allows the AI to pin notes to a host dashboard (e.g., "AI Note: Detected CPU spike, investigating...").

## 3. Remote Execution via SSH (Auto-Remediation)
To allow the agent to actually fix broken servers (like restarting a crashed web service), we will introduce a secure SSH layer.
* **`paramiko` Integration:** Install the `paramiko` Python library.
* **Tool Creation:** Create a tool `@tool def execute_remote_command(hostname, command)`.
* **Constraint:** The agent will only be allowed to run a predefined whitelist of safe commands (e.g., `systemctl restart nginx`, `systemctl status docker`, `df -h`). It will be explicitly forbidden from running arbitrary shell code like `rm -rf`.

## 4. Bulk Configuration Management (Icinga Director Integration)
Instead of modifying single hosts, Phase 2 will allow the agent to build monitoring config.
* **Director API:** The agent will interact with the Icinga Director REST API (which is different from the core Icinga 2 API).
* **Tool Creation:** `@tool def create_host(hostname, ip_address, template)`. This will allow the user to say *"Add these 5 new IP addresses to the web-server group"* and the AI will generate and push the configuration automatically.

## 5. Agent Logic Update (`agent.py`)
* Add the new tools to the LangChain executor.
* **Prompt Engineering Upgrade:** Update the system prompt to explicitly state: *"If you detect a known issue and have a remediation tool available, ask the user for permission to execute the fix. If the user asks to schedule downtime, execute the downtime tool."*

## Execution Strategy
We will implement these one by one. Our first target will be **Automated Alert Acknowledgement**, as it is the easiest to test, has the lowest risk, and provides immediate value to the operations team!
