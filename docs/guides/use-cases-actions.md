# Use Cases: Action-Capable Management Agent (Phase 2)

The Action-Capable Agent (AIOps) transitions from a passive observer to an active participant. It has the authority to make changes via `POST` requests to the Icinga 2 Actions API.

> **⚠️ Safety:** All action tools follow the Human-in-the-Loop (HITL) pattern — the agent always describes what it plans to do and asks for explicit user confirmation before executing. The Streamlit UI also renders approve/reject buttons for additional safety.

> **🔒 Security Note:** Action functions are in a separate module ([icinga_actions.py](../../icinga_actions.py)) from read functions ([icinga_api.py](../../icinga_api.py)) for clean security boundaries. In production, a dedicated `ai-action-user` with scoped API permissions should replace the root credentials.

---

## Implemented Action Use Cases

### 1. Acknowledge Problem
Stop Icinga from sending repeated notifications for a known issue. The acknowledgement remains until the problem resolves or is manually removed.

- **Prompt:** *"Acknowledge the ping alert on web-01."*
- **Example Conversation:**
  ```
  User: The HTTP service on web-01 is failing. Acknowledge it, the team knows.
  Agent: I'll acknowledge the HTTP problem on web-01. This will:
         - Stop repeated notifications for this issue
         - Mark it as acknowledged in Icinga Web 2
         Shall I proceed?
  User: Yes, proceed.
  Agent: ✅ Successfully acknowledged problem on web-01!http.
  ```
- **Tool:** `acknowledge_alert(hostname, service, comment)`
- **API Endpoint:** `POST /v1/actions/acknowledge-problem`
- **Parameters:** `type`, `filter`, `author`, `comment`, `notify`, `sticky`, `persistent`

### 2. Schedule Downtime
Schedule a maintenance window during which Icinga suppresses all notifications for a host (and optionally all its services).

- **Prompt:** *"Schedule 2 hours of downtime on db-master for a reboot."*
- **Example Conversation:**
  ```
  User: I'm going to reboot db-master tonight. Mute alerts for 4 hours.
  Agent: I'll schedule a 4-hour downtime on db-master:
         - Start: Now (2025-01-15 22:00)
         - End: 2025-01-16 02:00
         - All services on the host will also be muted.
         Shall I proceed?
  User: Yes.
  Agent: ✅ Successfully scheduled downtime on db-master from 2025-01-15 22:00 to 2025-01-16 02:00.
  ```
- **Tool:** `schedule_host_downtime(hostname, duration_hours, comment, service)`
- **API Endpoint:** `POST /v1/actions/schedule-downtime`
- **Parameters:** `type`, `filter`, `author`, `comment`, `start_time`, `end_time`, `duration`, `fixed`, `all_services`

### 3. Add Comment
Add an operational note or AI-generated insight to a host or service. Comments are visible to all operators in Icinga Web 2.

- **Prompt:** *"Add a comment to web-01: investigating slow response times."*
- **Example Conversation:**
  ```
  User: Add a note to the db-master host that we're investigating memory leaks.
  Agent: I'll add the following comment to db-master:
         "Investigating memory leaks — reported by operations team"
         This will be visible in Icinga Web 2. Shall I proceed?
  User: Go ahead.
  Agent: ✅ Successfully added comment to db-master: 'Investigating memory leaks — reported by operations team'
  ```
- **Tool:** `add_host_comment(hostname, comment, service)`
- **API Endpoint:** `POST /v1/actions/add-comment`
- **Parameters:** `type`, `filter`, `author`, `comment`

### 4. Remove Acknowledgement
Re-enable notifications for a previously acknowledged problem. Useful when an ack was premature or the issue was misidentified.

- **Prompt:** *"Remove the acknowledgement from the HTTP service on web-01."*
- **Example Conversation:**
  ```
  User: We acknowledged the SSH alert on db-master earlier but it turns out it's a real issue. Remove the ack.
  Agent: I'll remove the acknowledgement from db-master!ssh. This will:
         - Re-enable notifications for this problem
         - Icinga will resume alerting if the issue persists
         Shall I proceed?
  User: Yes.
  Agent: ✅ Successfully removed acknowledgement from db-master!ssh.
  ```
- **Tool:** `remove_alert_acknowledgement(hostname, service)`
- **API Endpoint:** `POST /v1/actions/remove-acknowledgement`
- **Parameters:** `type`, `filter`

### 5. Send Custom Notification
Force-send a notification to the on-call team about something the AI agent has discovered, even if Icinga wouldn't normally notify at this time.

- **Prompt:** *"Send a notification about the disk issue on web-01."*
- **Example Conversation:**
  ```
  User: I noticed disk usage on web-01 is growing 5% daily. Send a heads-up to the team.
  Agent: I'll send a custom notification for web-01 with the message:
         "AI Agent: Disk usage growing ~5% daily. Projected to hit capacity in 10 days."
         This will bypass notification filters and reach the on-call team. Shall I proceed?
  User: Yes, send it.
  Agent: ✅ Custom notification sent for web-01.
  ```
- **Tool:** `send_notification(hostname, comment, service)`
- **API Endpoint:** `POST /v1/actions/send-custom-notification`
- **Parameters:** `type`, `filter`, `author`, `comment`, `force`

### 6. Force Re-check
Trigger an immediate re-check of a host or service. Use this after making changes (restarted a service, cleared disk space) to verify the fix without waiting for the next scheduled check interval.

- **Prompt:** *"Force a re-check of the SSH service on db-master."*
- **Example Conversation:**
  ```
  User: I just restarted nginx on web-01. Can you check if it's back up?
  Agent: I'll force an immediate re-check of web-01!nginx.
         This overrides the normal check interval and runs the check right now.
         Shall I proceed?
  User: Yes.
  Agent: ✅ Forced immediate re-check of web-01!nginx.
         [Agent then automatically calls get_service_details to report the new state]
  ```
- **Tool:** `force_recheck(hostname, service)`
- **API Endpoint:** `POST /v1/actions/reschedule-check`
- **Parameters:** `type`, `filter`, `next_check`, `force_check`

---

## Future Action Use Cases (Planned)

### 7. Auto-Remediation (Self-Healing Infrastructure)
The agent intercepts alerts and attempts safe fixes (e.g., `systemctl restart nginx`) via SSH before waking up a human. *(Requires `paramiko` — added to requirements.txt)*

### 8. Bulk Onboarding and Configuration Management
Add new hosts to monitoring conversationally via the Icinga Director API.

### 9. Smart Capacity Planning and Resizing
Combine historical metrics with action capabilities to manage cloud resources proactively.

---

## HITL Safety Architecture

```
User Request → Agent Analyzes → Agent Describes Plan → User Confirms → Agent Executes → Agent Reports Result
                                        ↑                    ↑
                                  System Prompt          Streamlit UI
                                  Safety Rules           ✅/❌ Buttons
```

The HITL safety pattern operates at two levels:
1. **Prompt-level:** The system prompt instructs the agent to always describe and confirm before acting.
2. **UI-level:** Streamlit detects confirmation-like phrases in the agent's response and renders approve/reject buttons.
