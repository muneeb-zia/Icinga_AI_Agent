"""
Enterprise Role-Based Access Control (RBAC) & AI Tool-Gating Security Engine
Enforces tiered security permissions (L1 to L4) across AI function-calling actions:
1. L1 (NOC Tier 1 / Read-Only): Telemetry querying, alert search, runbook RAG. No state modifications.
2. L2 (NOC Tier 2 / Operator): Acknowledge alerts, schedule downtimes, add comments.
3. L3 (Senior SRE / Engineer): Service restarts, active force rechecks, safe script execution.
4. L4 (Admin / Platform Lead): Full administrative power, user provisioning, BPM tree modifications.
"""

import sys
import os
import json
import enum
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class RBACRole(enum.IntEnum):
    L1_READONLY = 1
    L2_OPERATOR = 2
    L3_SRE_ENGINEER = 3
    L4_PLATFORM_ADMIN = 4

    @classmethod
    def from_str(cls, role_str: str) -> "RBACRole":
        s = role_str.upper().strip()
        if "1" in s or "READ" in s:
            return cls.L1_READONLY
        elif "2" in s or "OPERATOR" in s:
            return cls.L2_OPERATOR
        elif "3" in s or "SRE" in s or "ENGINEER" in s:
            return cls.L3_SRE_ENGINEER
        elif "4" in s or "ADMIN" in s or "LEAD" in s:
            return cls.L4_PLATFORM_ADMIN
        return cls.L1_READONLY


@dataclass
class User:
    user_id: str
    username: str
    role: RBACRole
    email: str
    department: str = "NOC Operations"
    is_active: bool = True
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))


@dataclass
class SecurityAuditRecord:
    timestamp: str
    user_id: str
    username: str
    user_role: str
    tool_name: str
    required_role: str
    authorized: bool
    reason: str
    parameters_summary: str


class RBACManager:
    """
    Enterprise Security Manager enforcing RBAC at the AI agent tool-execution level.
    """
    AUDIT_FILE = "rbac_audit_log.json"

    # Strict AI Tool-to-Permission Mapping Matrix
    TOOL_PERMISSIONS: Dict[str, RBACRole] = {
        # --- L1 READ-ONLY TOOLS (Level 1+) ---
        "search_runbooks": RBACRole.L1_READONLY,
        "search_knowledge_base": RBACRole.L1_READONLY,
        "get_host_status": RBACRole.L1_READONLY,
        "get_service_status": RBACRole.L1_READONLY,
        "query_opensearch_logs": RBACRole.L1_READONLY,
        "query_metrics": RBACRole.L1_READONLY,
        "get_bpm_tree_status": RBACRole.L1_READONLY,
        "generate_report_preview": RBACRole.L1_READONLY,

        # --- L2 OPERATOR TOOLS (Level 2+) ---
        "acknowledge_alert": RBACRole.L2_OPERATOR,
        "remove_acknowledgement": RBACRole.L2_OPERATOR,
        "schedule_host_downtime": RBACRole.L2_OPERATOR,
        "schedule_service_downtime": RBACRole.L2_OPERATOR,
        "add_incident_comment": RBACRole.L2_OPERATOR,
        "send_notification_card": RBACRole.L2_OPERATOR,
        "add_host_comment": RBACRole.L2_OPERATOR,
        "remove_alert_acknowledgement": RBACRole.L2_OPERATOR,
        "send_notification": RBACRole.L2_OPERATOR,

        # --- L3 SENIOR SRE TOOLS (Level 3+) ---
        "restart_service": RBACRole.L3_SRE_ENGINEER,
        "force_recheck": RBACRole.L3_SRE_ENGINEER,
        "execute_remediation_command": RBACRole.L3_SRE_ENGINEER,
        "kill_runaway_process": RBACRole.L3_SRE_ENGINEER,
        "drop_page_cache": RBACRole.L3_SRE_ENGINEER,
        "scale_deployment": RBACRole.L3_SRE_ENGINEER,
        "create_hostgroup": RBACRole.L3_SRE_ENGINEER,
        "create_host_template": RBACRole.L3_SRE_ENGINEER,
        "onboard_new_host": RBACRole.L3_SRE_ENGINEER,
        "create_servicegroup": RBACRole.L3_SRE_ENGINEER,
        "create_service_template": RBACRole.L3_SRE_ENGINEER,
        "create_service": RBACRole.L3_SRE_ENGINEER,
        "create_serviceset": RBACRole.L3_SRE_ENGINEER,
        "create_check_command": RBACRole.L3_SRE_ENGINEER,

        # --- L4 PLATFORM ADMIN TOOLS (Level 4 ONLY) ---
        "create_user": RBACRole.L4_PLATFORM_ADMIN,
        "delete_user": RBACRole.L4_PLATFORM_ADMIN,
        "modify_bpm_hierarchy": RBACRole.L4_PLATFORM_ADMIN,
        "deploy_icinga_director_config": RBACRole.L4_PLATFORM_ADMIN,
        "deploy_director_config": RBACRole.L4_PLATFORM_ADMIN,
        "bulk_remediate_hosts": RBACRole.L4_PLATFORM_ADMIN,
        "export_audit_logs": RBACRole.L4_PLATFORM_ADMIN
    }

    def __init__(self, initial_users: Optional[List[User]] = None):
        self.users: Dict[str, User] = {}
        self.audit_log: List[SecurityAuditRecord] = []
        
        # Seed default enterprise users across all 4 tiers including Icinga Web 2 accounts
        defaults = initial_users or [
            User("admin", "admin", RBACRole.L4_PLATFORM_ADMIN, "admin@company.com", "Platform Engineering Lead"),
            User("senior_sre", "senior_sre", RBACRole.L2_OPERATOR, "sre@company.com", "NOC Tier 2 Operator"),
            User("junior_operator", "junior_operator", RBACRole.L1_READONLY, "junior@company.com", "NOC Tier 1 Junior"),
            User("usr_l1_junior", "alex.intern", RBACRole.L1_READONLY, "alex@company.com", "NOC Tier 1"),
            User("usr_l2_operator", "sam.operator", RBACRole.L2_OPERATOR, "sam@company.com", "NOC Tier 2"),
            User("usr_l3_sre", "elena.sre", RBACRole.L3_SRE_ENGINEER, "elena@company.com", "Site Reliability Engineering"),
            User("usr_l4_admin", "marcus.lead", RBACRole.L4_PLATFORM_ADMIN, "marcus@company.com", "Platform Engineering Lead")
        ]
        for u in defaults:
            self.users[u.user_id] = u
            self.users[u.username] = u

    def register_user(self, user_id: str, username: str, role: RBACRole, email: str, dept: str = "NOC") -> User:
        user = User(user_id, username, role, email, dept)
        self.users[user_id] = user
        self.users[username] = user
        return user

    def get_user(self, user_id_or_name: str) -> Optional[User]:
        if user_id_or_name in self.users:
            return self.users[user_id_or_name]
        for u in self.users.values():
            if u.username.lower() == user_id_or_name.lower() or u.user_id.lower() == user_id_or_name.lower():
                return u
        return None

    def check_permission(self, user_id: str, tool_name: str, tool_args: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Validates whether user has sufficient security clearance to invoke a tool.
        Returns: (is_authorized: bool, explanation: str)
        """
        user = self.users.get(user_id)
        if not user or not user.is_active:
            return False, f"Authentication Error: User ID '{user_id}' does not exist or is inactive."

        required_role = self.TOOL_PERMISSIONS.get(tool_name, RBACRole.L4_PLATFORM_ADMIN)

        param_str = json.dumps(tool_args or {})[:120]
        now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        # Check hierarchy: user.role >= required_role
        if user.role >= required_role:
            record = SecurityAuditRecord(
                timestamp=now_str,
                user_id=user.user_id,
                username=user.username,
                user_role=user.role.name,
                tool_name=tool_name,
                required_role=required_role.name,
                authorized=True,
                reason="Authorization Granted: Sufficient clearance level.",
                parameters_summary=param_str
            )
            self.audit_log.append(record)
            return True, f"Permission granted for {user.username} ({user.role.name}) -> {tool_name}"
        else:
            record = SecurityAuditRecord(
                timestamp=now_str,
                user_id=user.user_id,
                username=user.username,
                user_role=user.role.name,
                tool_name=tool_name,
                required_role=required_role.name,
                authorized=False,
                reason=f"SECURITY VIOLATION: User role {user.role.name} is insufficient. Requires {required_role.name}.",
                parameters_summary=param_str
            )
            self.audit_log.append(record)
            return False, f"SECURITY GATE BLOCKED: User '{user.username}' ({user.role.name}) attempted to invoke '{tool_name}' which requires clearance '{required_role.name}'."

    def execute_gated_tool(
        self,
        user_id: str,
        tool_name: str,
        tool_callable: Callable,
        tool_args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Executes a tool with strict RBAC enforcement wrapper."""
        allowed, msg = self.check_permission(user_id, tool_name, tool_args)
        if not allowed:
            return {
                "status": "SECURITY_ERROR",
                "authorized": False,
                "error_code": "ERR_RBAC_UNAUTHORIZED",
                "message": msg,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }

        try:
            args = tool_args or {}
            result = tool_callable(**args)
            return {
                "status": "SUCCESS",
                "authorized": True,
                "tool_name": tool_name,
                "result": result
            }
        except Exception as e:
            return {
                "status": "EXECUTION_ERROR",
                "authorized": True,
                "error": str(e)
            }

    def export_audit_log(self, file_path: Optional[str] = None) -> str:
        out_path = file_path or os.path.join(os.path.dirname(__file__), self.AUDIT_FILE)
        records = [asdict(r) for r in self.audit_log]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"total_audited_events": len(records), "events": records}, f, indent=2)
        return out_path


if __name__ == "__main__":
    print("================================================================================")
    print("🚀 TESTING ENTERPRISE RBAC & AI TOOL-GATING SECURITY MATRIX")
    print("================================================================================")

    rbac = RBACManager()

    # Mock tool functions
    def dummy_read_metrics(hostname: str):
        return f"Metrics for {hostname}: CPU 88%, RAM 94%"

    def dummy_ack_alert(hostname: str, comment: str):
        return f"Acknowledged alert on {hostname}: '{comment}'"

    def dummy_restart_service(hostname: str, service: str):
        return f"Service '{service}' restarted successfully on {hostname} via systemctl."

    def dummy_deploy_config():
        return "Icinga Director Config v2.4 deployed across cluster."

    print("\n--- TEST 1: L1 JUNIOR INTERN ATTEMPTS TO READ METRICS (Allowed) ---")
    res1 = rbac.execute_gated_tool("usr_l1_junior", "query_metrics", dummy_read_metrics, {"hostname": "web-prod-01"})
    print(f"Status: {res1['status']} | Output: {res1.get('result')}")

    print("\n--- TEST 2: L1 JUNIOR INTERN ATTEMPTS TO RESTART SERVICE (BLOCKED!) ---")
    res2 = rbac.execute_gated_tool("usr_l1_junior", "restart_service", dummy_restart_service, {"hostname": "web-prod-01", "service": "mysql"})
    print(f"Status: {res2['status']} | Message: {res2['message']}")

    print("\n--- TEST 3: L2 OPERATOR ATTEMPTS TO ACKNOWLEDGE ALERT (Allowed) ---")
    res3 = rbac.execute_gated_tool("usr_l2_operator", "acknowledge_alert", dummy_ack_alert, {"hostname": "web-prod-01", "comment": "Investigating high load"})
    print(f"Status: {res3['status']} | Output: {res3.get('result')}")

    print("\n--- TEST 4: L2 OPERATOR ATTEMPTS TO DEPLOY DIRECTOR CONFIG (BLOCKED!) ---")
    res4 = rbac.execute_gated_tool("usr_l2_operator", "deploy_icinga_director_config", dummy_deploy_config)
    print(f"Status: {res4['status']} | Message: {res4['message']}")

    print("\n--- TEST 5: L3 SENIOR SRE RESTARTS SERVICE (Allowed) ---")
    res5 = rbac.execute_gated_tool("usr_l3_sre", "restart_service", dummy_restart_service, {"hostname": "web-prod-01", "service": "nginx"})
    print(f"Status: {res5['status']} | Output: {res5.get('result')}")

    print("\n--- TEST 6: L4 PLATFORM ADMIN DEPLOYS DIRECTOR CONFIG (Allowed) ---")
    res6 = rbac.execute_gated_tool("usr_l4_admin", "deploy_icinga_director_config", dummy_deploy_config)
    print(f"Status: {res6['status']} | Output: {res6.get('result')}")

    audit_path = rbac.export_audit_log()
    print(f"\n🔒 Security Audit Trail saved with {len(rbac.audit_log)} events to: {audit_path}")
