"""
Smart Notification Engine & Tier-Specific Team Routing
Formats context-aware alert notifications specifically tailored for:
1. DevOps / SRE Team: Telemetry metrics, threshold graphs, pod logs, rollback commands
2. Development Team: Exception stack traces, git commit tags, endpoint URIs
3. Infrastructure Team: Hypervisor telemetry, switch port stats, bare-metal sensors
4. Executive / Management: SLA impact, user impact summary, high-level status
"""

import sys
import json
import enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class TeamRole(enum.Enum):
    DEVOPS_SRE = "DevOps/SRE Team"
    DEVELOPMENT = "Development Team"
    INFRASTRUCTURE = "Infrastructure & Systems Team"
    SECURITY_NOC = "Security & NOC Operations"
    EXECUTIVE = "Executive Leadership"


@dataclass
class AlertPayload:
    alert_id: str
    hostname: str
    service: str
    state: str  # "CRITICAL", "WARNING", "UNKNOWN", "OK"
    output: str
    timestamp: str
    environment: str = "production"
    cluster_id: str = "cluster-eu-west-1"
    
    # SRE / Performance Telemetry
    metrics: Dict[str, Any] = field(default_factory=dict)
    container_info: Dict[str, Any] = field(default_factory=dict)
    suggested_commands: List[str] = field(default_factory=list)
    
    # Developer / Application Info
    exception_type: Optional[str] = None
    stack_trace: Optional[str] = None
    endpoint_url: Optional[str] = None
    git_commit_sha: Optional[str] = None
    repo_url: Optional[str] = None
    
    # Infrastructure / Hardware Info
    hypervisor_id: Optional[str] = None
    rack_unit: Optional[str] = None
    switch_port: Optional[str] = None
    disk_iops: Optional[Dict[str, Any]] = None


@dataclass
class FormattedNotification:
    recipient_team: TeamRole
    title: str
    priority: str
    summary: str
    formatted_body_markdown: str
    formatted_body_html: str
    teams_card_json: Dict[str, Any]
    slack_blocks_json: Dict[str, Any]
    suggested_actions: List[str]


class SmartNotificationRouter:
    """
    Intelligently classifies alert context and routes tailored notification payloads
    to the responsible engineering teams.
    """

    @classmethod
    def classify_target_team(cls, alert: AlertPayload) -> TeamRole:
        """Determines the primary responsible engineering team based on telemetry & error signatures."""
        service_lower = alert.service.lower()
        output_lower = alert.output.lower()

        # 1. Developer App Errors (Exceptions, 500s, Stack Traces)
        if alert.stack_trace or alert.exception_type or "nullpointer" in output_lower or "traceback" in output_lower:
            return TeamRole.DEVELOPMENT
        if "http" in service_lower and ("500" in output_lower or "exception" in output_lower or "internal server error" in output_lower):
            return TeamRole.DEVELOPMENT

        # 2. Infrastructure / Hardware / Network
        if any(kw in service_lower for kw in ["ping", "switch", "pdu", "ipmi", "raid", "interface", "hardware"]):
            return TeamRole.INFRASTRUCTURE
        if any(kw in output_lower for kw in ["packet loss", "kernel panic", "ecc memory error", "smart status bad"]):
            return TeamRole.INFRASTRUCTURE

        # 3. Security
        if any(kw in service_lower or kw in output_lower for kw in ["ssh brute", "unauthorized", "waf", "cert expired", "firewall"]):
            return TeamRole.SECURITY_NOC

        # 4. Default: DevOps / SRE (Capacity, CPU, RAM, Disk, Containers, DB, Ingress)
        return TeamRole.DEVOPS_SRE

    @classmethod
    def format_notification(cls, alert: AlertPayload, target_team: Optional[TeamRole] = None) -> FormattedNotification:
        """Renders the team-specific notification template."""
        team = target_team or cls.classify_target_team(alert)
        state_icon = {"CRITICAL": "🚨", "WARNING": "⚠️", "OK": "✅", "UNKNOWN": "❓"}.get(alert.state, "ℹ️")
        priority = "P1 - HIGH" if alert.state == "CRITICAL" else "P2 - MEDIUM" if alert.state == "WARNING" else "P3 - LOW"

        title = f"{state_icon} [{alert.state}] {alert.hostname} :: {alert.service}"

        # ---------------------------------------------------------------------
        # A. DEVOPS / SRE TEMPLATE
        # ---------------------------------------------------------------------
        if team == TeamRole.DEVOPS_SRE:
            metrics_str = "\n".join([f"- **{k}**: `{v}`" for k, v in alert.metrics.items()]) if alert.metrics else "- No raw metrics attached"
            cmds_str = "\n".join([f"```bash\n{cmd}\n```" for cmd in alert.suggested_commands]) if alert.suggested_commands else "```bash\nicingacli alert check --host " + alert.hostname + "\n```"
            container_str = f"- **Pod/Container**: `{alert.container_info.get('pod_name', 'N/A')}` | **Restarts**: `{alert.container_info.get('restart_count', 0)}`" if alert.container_info else ""

            body_md = f"""### 🛠️ SRE Incident Telemetry & Diagnostic Briefing
**Target Host**: `{alert.hostname}` | **Env**: `{alert.environment}` | **Cluster**: `{alert.cluster_id}`
**Trigger Output**: `{alert.output}`

#### 📊 Telemetry & Resource Pressure:
{metrics_str}
{container_str}

#### ⚡ Automated Diagnostic & Rollback Commands:
{cmds_str}
"""
            actions = alert.suggested_commands or ["systemctl status", "kubectl describe pod", "force_recheck"]

        # ---------------------------------------------------------------------
        # B. DEVELOPMENT TEAM TEMPLATE
        # ---------------------------------------------------------------------
        elif team == TeamRole.DEVELOPMENT:
            exc_str = alert.exception_type or "Unhandled Application Exception"
            trace_str = alert.stack_trace or alert.output
            commit_str = f"**Git Commit**: [{alert.git_commit_sha[:8]}]({alert.repo_url}/commit/{alert.git_commit_sha})" if alert.git_commit_sha and alert.repo_url else f"**Commit SHA**: `{alert.git_commit_sha or 'N/A'}`"
            url_str = f"**Endpoint**: `{alert.endpoint_url}`" if alert.endpoint_url else ""

            body_md = f"""### 💻 Application Exception & Traceback Report
**Host/Pod**: `{alert.hostname}` | **Environment**: `{alert.environment}`
{url_str}
{commit_str}

#### 💥 Exception Details:
**Type**: `{exc_str}`
```python
{trace_str[:600]}
```

#### 🔍 Action Required:
Inspect recent pull request deployments matching commit `{alert.git_commit_sha or 'HEAD'}` and check error budgets.
"""
            actions = ["Inspect Exception Sentry/Logs", "Revert Last Git Release", "Check Endpoint Response"]

        # ---------------------------------------------------------------------
        # C. INFRASTRUCTURE & SYSTEMS TEMPLATE
        # ---------------------------------------------------------------------
        elif team == TeamRole.INFRASTRUCTURE:
            body_md = f"""### 🏗️ Bare-Metal & Network Infrastructure Alert
**Host**: `{alert.hostname}` | **Rack**: `{alert.rack_unit or 'DC-Row4-Rack12'}`
**Hypervisor**: `{alert.hypervisor_id or 'esxi-node-04.infra.internal'}`
**Switch Port**: `{alert.switch_port or 'eth0 -> Sw-Core-01:Gig1/0/24'}`

#### 🔌 Hardware & Link Diagnostic Output:
`{alert.output}`

#### 🔧 Field Engineering Actions:
1. Verify physical switch port link status and transceiver CRC errors.
2. Check IPMI/iLO remote console for hardware watchdog timeouts.
3. If node is unrecoverable, initiate live VM migration off `{alert.hypervisor_id or 'host'}`.
"""
            actions = ["IPMI Power Cycle", "Check Switch Interface", "Migrate Virtual Machines"]

        # ---------------------------------------------------------------------
        # D. EXECUTIVE / MANAGEMENT TEMPLATE
        # ---------------------------------------------------------------------
        else:
            body_md = f"""### 👔 Executive Incident Impact Summary
**Service Affected**: `{alert.service}` on `{alert.hostname}`
**Severity**: `{alert.state}` ({priority})
**Business Impact**: Critical user transaction flow degraded.
**Status**: Autonomous diagnostic in progress; SRE team dispatched.
"""
            actions = ["View Executive Dashboard", "Subscribe to Incident Updates"]

        # ---------------------------------------------------------------------
        # RENDER TEAMS & SLACK JSON CARDS
        # ---------------------------------------------------------------------
        teams_card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "color": "Attention" if alert.state == "CRITICAL" else "Warning"},
                {"type": "TextBlock", "text": f"Routed to: **{team.value}** ({priority})", "isSubtle": True},
                {"type": "TextBlock", "text": alert.output, "wrap": True},
                {"type": "FactSet", "facts": [
                    {"title": "Host", "value": alert.hostname},
                    {"title": "Environment", "value": alert.environment},
                    {"title": "Timestamp", "value": alert.timestamp}
                ]}
            ],
            "actions": [
                {"type": "Action.Submit", "title": "Acknowledge Alert", "data": {"action": "ack", "alert_id": alert.alert_id}},
                {"type": "Action.Submit", "title": "Trigger Force Recheck", "data": {"action": "recheck", "alert_id": alert.alert_id}}
            ]
        }

        slack_blocks = {
            "text": title,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": title, "emoji": True}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Team:* `{team.value}`"},
                        {"type": "mrkdwn", "text": f"*Priority:* `{priority}`"},
                        {"type": "mrkdwn", "text": f"*Host:* `{alert.hostname}`"},
                        {"type": "mrkdwn", "text": f"*Environment:* `{alert.environment}`"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{alert.output}```"}
                }
            ]
        }

        # HTML Formatted Body
        body_html = f"""
        <div style="font-family: Arial, sans-serif; border-left: 4px solid {'#E74C3C' if alert.state=='CRITICAL' else '#F39C12'}; padding-left: 15px;">
            <h2 style="color: {'#C0392B' if alert.state=='CRITICAL' else '#D35400'};">{title}</h2>
            <p><strong>Routed To:</strong> {team.value} | <strong>Priority:</strong> {priority}</p>
            <div style="background-color: #f4f6f7; padding: 10px; border-radius: 4px; font-family: monospace;">{alert.output}</div>
        </div>
        """

        return FormattedNotification(
            recipient_team=team,
            title=title,
            priority=priority,
            summary=alert.output[:120],
            formatted_body_markdown=body_md,
            formatted_body_html=body_html,
            teams_card_json=teams_card,
            slack_blocks_json=slack_blocks,
            suggested_actions=actions
        )


if __name__ == "__main__":
    print("================================================================================")
    print("🚀 TESTING SMART NOTIFICATION ROUTER ACROSS 3 ENGINEERING TIERS")
    print("================================================================================")

    # 1. SRE Case: High Memory & OOM
    sre_alert = AlertPayload(
        alert_id="ALT-101",
        hostname="k8s-worker-prod-04",
        service="check_mem",
        state="CRITICAL",
        output="CRITICAL - Memory usage: 98.4% (Free: 120MB). OOM Killer active.",
        timestamp="2026-08-28 15:30:00 UTC",
        metrics={"used_mem_percent": 98.4, "swap_used_mb": 4096, "oom_events_total": 3},
        container_info={"pod_name": "billing-service-7b6c89-pxz", "restart_count": 5},
        suggested_commands=["kubectl describe pod billing-service-7b6c89-pxz", "kubectl rollout restart deployment/billing-service"]
    )
    sre_notif = SmartNotificationRouter.format_notification(sre_alert)
    print(f"\n[TEST 1] SRE Alert Formatted for: {sre_notif.recipient_team.value}")
    print(sre_notif.formatted_body_markdown)

    # 2. Developer Case: NullPointer / Stack Trace
    dev_alert = AlertPayload(
        alert_id="ALT-102",
        hostname="api-gateway-01",
        service="HTTP API /v1/checkout",
        state="CRITICAL",
        output="HTTP 500 Internal Server Error - NullPointerException in PaymentProcessor.java:142",
        timestamp="2026-08-28 15:31:00 UTC",
        exception_type="java.lang.NullPointerException",
        stack_trace="at com.ecommerce.payment.PaymentProcessor.processTransaction(PaymentProcessor.java:142)\n   at com.ecommerce.api.CheckoutController.handlePost(CheckoutController.java:58)",
        endpoint_url="https://api.ecommerce.com/v1/checkout",
        git_commit_sha="a7f83b9248df912",
        repo_url="https://github.com/ecommerce/payment-service"
    )
    dev_notif = SmartNotificationRouter.format_notification(dev_alert)
    print(f"\n[TEST 2] Dev Alert Formatted for: {dev_notif.recipient_team.value}")
    print(dev_notif.formatted_body_markdown)

    # 3. Infrastructure Case: Core Switch Packet Loss
    infra_alert = AlertPayload(
        alert_id="ALT-103",
        hostname="sw-core-dc01-spine",
        service="check_ping",
        state="CRITICAL",
        output="CRITICAL - 65% packet loss on VLAN 100 interface TenGig0/1/1",
        timestamp="2026-08-28 15:32:00 UTC",
        rack_unit="DC-Row01-Rack04",
        hypervisor_id="baremetal-switch-spine-01",
        switch_port="TenGig0/1/1 -> Core Trunk"
    )
    infra_notif = SmartNotificationRouter.format_notification(infra_alert)
    print(f"\n[TEST 3] Infra Alert Formatted for: {infra_notif.recipient_team.value}")
    print(infra_notif.formatted_body_markdown)
