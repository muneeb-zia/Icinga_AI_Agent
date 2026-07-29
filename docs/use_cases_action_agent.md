# Use Cases: Action-Capable Management Agent (Phase 2)

The Action-Capable Agent (AIOps) transitions from a passive observer to an active participant. It has the authority to make changes via `POST`/`PUT` requests to the Icinga API or execute scripts on remote servers.

## 1. Automated Alert Acknowledgement and Ticketing
The agent handles the tedious paperwork of incident management automatically.
- **Scenario:** A known, low-priority backup server runs out of disk space.
- **Execution:** The agent automatically acknowledges the alert in Icinga (so it stops paging people), creates a Jira/ServiceNow ticket with the exact disk metrics, and replies to the Slack channel: *"I saw the backup server is full. I acknowledged the alert and created Ticket #1234 for the storage team."*

## 2. Frictionless Scheduled Downtime
Scheduling downtime manually requires navigating menus and calculating timestamps. The agent does it conversationally.
- **Prompt:** *"I'm going to reboot the database cluster tonight at 2 AM for maintenance. Mute alerts for 4 hours."*
- **Execution:** The agent calculates the epoch timestamps for 2 AM to 6 AM, formats the JSON payload, and POSTs it to the `/v1/actions/schedule-downtime` endpoint for all hosts in the cluster.

## 3. Auto-Remediation (Self-Healing Infrastructure)
The agent acts as a Level 2 automated engineer, attempting safe fixes before waking up a human.
- **Scenario:** Icinga detects that the `nginx` web service has crashed on a server.
- **Execution:** The agent intercepts the alert, uses an SSH tool (or Icinga's remote execution API) to run `systemctl restart nginx`. It then waits 30 seconds, verifies via the Icinga API that the service is UP again, and logs the action: *"Nginx crashed on web-01. I automatically restarted the service and it is healthy again."*

## 4. Bulk Onboarding and Configuration Management
Instead of manually writing Icinga configuration files, the agent acts as an interface to the Icinga Director API.
- **Prompt:** *"We just bought 5 new Dell R740 servers for the web farm. Their IPs are 10.0.0.50 through 55. Add them to monitoring."*
- **Execution:** The agent generates the JSON payloads and pushes them to Icinga Director, applying the "Linux Web Server" template to all 5 IPs automatically.

## 5. Smart Capacity Planning and Resizing
By combining historical Graphite metrics with Action capabilities, the agent can manage cloud resources.
- **Scenario:** The agent notices that a database server's CPU has been hitting 95% every day during business hours for a week.
- **Execution:** The agent alerts the user: *"DB-01 is consistently CPU starved. Would you like me to trigger the Terraform/AWS script to resize the instance to a larger instance type tonight at midnight?"* Upon user approval, it executes the resizing script.
