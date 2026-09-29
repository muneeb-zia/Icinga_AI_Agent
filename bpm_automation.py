"""
Business Process Module (BPM) Tree Auto-Generation & Hierarchy Management Engine
Automates:
1. Template-based host & service discovery (e.g., tpl-webserver, tpl-mysql-cluster, tpl-k8s-worker)
2. Dynamic Parent-Child Directed Acyclic Graph (DAG) construction
3. Enterprise Redundancy & Quorum Logic (e.g., K-of-N nodes online)
4. State Rollup calculation (Best-of-N, Worst-of-N, Quorum)
5. Icinga Director BPM JSON & DSL configuration export
"""

import json
import enum
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Set

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")



class BPMState(enum.Enum):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3

    @classmethod
    def from_str(cls, state_str: str) -> "BPMState":
        s = state_str.upper().strip()
        if s in {"OK", "UP", "HEALTHY", "0"}:
            return cls.OK
        elif s in {"WARNING", "DEGRADED", "WARN", "1"}:
            return cls.WARNING
        elif s in {"CRITICAL", "DOWN", "FATAL", "2"}:
            return cls.CRITICAL
        else:
            return cls.UNKNOWN


class RollupRule(enum.Enum):
    QUORUM = "QUORUM"         # K of N nodes healthy (e.g. 2 of 3)
    WORST_STATE = "WORST"     # If any child fails, parent reflects worst state
    BEST_STATE = "BEST"       # If at least one child is healthy, parent is OK


@dataclass
class BPMNode:
    id: str
    name: str
    node_type: str  # "BUSINESS_PROCESS", "BUSINESS_SERVICE", "COMPONENT_GROUP", "HOST_LEAF", "SERVICE_LEAF"
    state: BPMState = BPMState.OK
    children_ids: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    rollup_rule: RollupRule = RollupRule.WORST_STATE
    quorum_k: int = 1  # Required healthy nodes for QUORUM rule
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    state_reason: str = "Initialized healthy"


class BPMHierarchy:
    """Manages the Directed Acyclic Graph (DAG) of Business Process Nodes."""
    def __init__(self, process_id: str, name: str):
        self.process_id = process_id
        self.name = name
        self.root_id = process_id
        self.nodes: Dict[str, BPMNode] = {}
        
        # Create root process node
        root = BPMNode(
            id=process_id,
            name=name,
            node_type="BUSINESS_PROCESS",
            rollup_rule=RollupRule.WORST_STATE,
            description=f"Root Business Process: {name}"
        )
        self.nodes[process_id] = root

    def add_node(self, node: BPMNode, parent_id: Optional[str] = None) -> None:
        self.nodes[node.id] = node
        p_id = parent_id or self.root_id
        if p_id in self.nodes:
            node.parent_id = p_id
            if node.id not in self.nodes[p_id].children_ids:
                self.nodes[p_id].children_ids.append(node.id)

    def get_node(self, node_id: str) -> Optional[BPMNode]:
        return self.nodes.get(node_id)

    def evaluate_state(self, node_id: Optional[str] = None) -> BPMState:
        """
        Recursively calculates the state of nodes from leaf to root.
        Implements Quorum, Worst-State, and Best-State rollups.
        """
        target_id = node_id or self.root_id
        node = self.nodes.get(target_id)
        if not node:
            return BPMState.UNKNOWN

        # If it's a leaf node OR marked explicitly down without children evaluation
        if not node.children_ids:
            return node.state

        # If a host itself was marked CRITICAL/DOWN, take the worst of its own state and its children
        child_states = [self.evaluate_state(c_id) for c_id in node.children_ids]
        if node.node_type == "HOST_LEAF" and node.state == BPMState.CRITICAL:
            child_states.append(BPMState.CRITICAL)

        ok_count = child_states.count(BPMState.OK)
        warn_count = child_states.count(BPMState.WARNING)
        crit_count = child_states.count(BPMState.CRITICAL)
        total_children = len(child_states)


        if node.rollup_rule == RollupRule.WORST_STATE:
            if BPMState.CRITICAL in child_states:
                node.state = BPMState.CRITICAL
                node.state_reason = f"Degraded: {crit_count} child node(s) in CRITICAL state."
            elif BPMState.WARNING in child_states:
                node.state = BPMState.WARNING
                node.state_reason = f"Warning: {warn_count} child node(s) in WARNING state."
            elif BPMState.UNKNOWN in child_states and ok_count == 0:
                node.state = BPMState.UNKNOWN
                node.state_reason = "Unknown: All children in UNKNOWN state."
            else:
                node.state = BPMState.OK
                node.state_reason = "All child dependencies healthy."

        elif node.rollup_rule == RollupRule.BEST_STATE:
            if BPMState.OK in child_states:
                node.state = BPMState.OK
                node.state_reason = f"Healthy: At least one replica active ({ok_count}/{total_children} OK)."
            elif BPMState.WARNING in child_states:
                node.state = BPMState.WARNING
                node.state_reason = "Warning: Best child replica is in WARNING."
            else:
                node.state = BPMState.CRITICAL
                node.state_reason = "Critical: All redundant replica instances down."

        elif node.rollup_rule == RollupRule.QUORUM:
            required_k = max(1, node.quorum_k)
            if ok_count >= required_k:
                node.state = BPMState.OK
                node.state_reason = f"Quorum Satisfied: {ok_count}/{total_children} nodes online (Threshold: {required_k})."
            elif ok_count + warn_count >= required_k:
                node.state = BPMState.WARNING
                node.state_reason = f"Quorum Warning: {ok_count} OK, {warn_count} Degraded (Quorum {required_k} met with warnings)."
            elif ok_count > 0:
                node.state = BPMState.WARNING
                node.state_reason = f"Quorum Breached: Only {ok_count}/{total_children} online (Need {required_k})."
            else:
                node.state = BPMState.CRITICAL
                node.state_reason = f"Quorum Lost: 0/{total_children} online (Need {required_k}). Entire cluster down."

        return node.state

    def simulate_state_change(self, node_id: str, new_state: BPMState) -> Dict[str, Any]:
        """Simulates an alert trigger on a leaf node and returns the cascading impact on root SLA."""
        if node_id in self.nodes:
            self.nodes[node_id].state = new_state
        root_state = self.evaluate_state()
        affected_node = self.nodes.get(node_id)
        return {
            "changed_node": node_id,
            "new_leaf_state": new_state.name,
            "cascaded_root_state": root_state.name,
            "root_reason": self.nodes[self.root_id].state_reason,
            "affected_node_reason": affected_node.state_reason if affected_node else ""
        }

    def export_icinga_config(self) -> Dict[str, Any]:
        """Exports hierarchy into Icinga Director Business Process Module JSON format."""
        tree_dict = {}
        for nid, node in self.nodes.items():
            tree_dict[nid] = {
                "display_name": node.name,
                "node_type": node.node_type,
                "state": node.state.name,
                "children": node.children_ids,
                "parent": node.parent_id,
                "rule": node.rollup_rule.value,
                "quorum_k": node.quorum_k if node.rollup_rule == RollupRule.QUORUM else None,
                "description": node.description,
                "metadata": node.metadata
            }
        return {
            "business_process": self.name,
            "process_id": self.process_id,
            "root_state": self.nodes[self.root_id].state.name,
            "nodes_count": len(self.nodes),
            "tree": tree_dict
        }

    def print_hierarchy(self, node_id: Optional[str] = None, prefix: str = "") -> None:
        """Visual tree print in console with ANSI color states."""
        target_id = node_id or self.root_id
        node = self.nodes.get(target_id)
        if not node:
            return

        state_symbol = {
            BPMState.OK: "🟢 [OK]",
            BPMState.WARNING: "🟡 [WARN]",
            BPMState.CRITICAL: "🔴 [CRIT]",
            BPMState.UNKNOWN: "⚪ [UNKN]"
        }.get(node.state, "❓")

        rule_info = f" ({node.rollup_rule.value}" + (f" {node.quorum_k} of {len(node.children_ids)}" if node.rollup_rule == RollupRule.QUORUM else "") + ")" if node.children_ids else ""
        print(f"{prefix}└── {state_symbol} {node.name}{rule_info} - {node.state_reason}")

        for idx, child_id in enumerate(node.children_ids):
            is_last = (idx == len(node.children_ids) - 1)
            new_prefix = prefix + ("    " if is_last else "│   ")
            self.print_hierarchy(child_id, new_prefix)


# =============================================================================
# AUTO-GENERATOR ENGINE (Transforms Provisioned Host Inventory into BPM Tree)
# =============================================================================

class BPMAutoBuilder:
    """
    Automated BPM Tree Builder.
    Reads host inventory or template configurations and automatically constructs
    standard enterprise business architectures.
    """
    TEMPLATE_MAPPINGS = {
        "tpl-webserver": {"tier": "Web Tier", "service": "HTTP/Frontend", "rule": RollupRule.QUORUM, "quorum_ratio": 0.6},
        "tpl-api-gateway": {"tier": "API Gateway Tier", "service": "API Gateway", "rule": RollupRule.QUORUM, "quorum_ratio": 0.6},
        "tpl-mysql-cluster": {"tier": "Database Tier", "service": "MySQL Database", "rule": RollupRule.QUORUM, "quorum_ratio": 0.66},
        "tpl-redis-cache": {"tier": "Cache Tier", "service": "Redis In-Memory Cache", "rule": RollupRule.BEST_STATE, "quorum_ratio": 0.5},
        "tpl-k8s-worker": {"tier": "Compute Cluster", "service": "K8s Microservices", "rule": RollupRule.QUORUM, "quorum_ratio": 0.75},
        "tpl-payment-gateway": {"tier": "Payment Service", "service": "Payment Processor", "rule": RollupRule.WORST_STATE, "quorum_ratio": 1.0}
    }

    @classmethod
    def build_enterprise_bpm(
        cls,
        business_process_name: str,
        host_inventory: List[Dict[str, Any]]
    ) -> BPMHierarchy:
        """
        Builds a full 3-tier BPM Tree from a list of provisioned host dictionaries.
        Each host item: {"hostname": str, "ip": str, "template": str, "environment": str, "services": list}
        """
        process_id = business_process_name.lower().replace(" ", "_")
        hierarchy = BPMHierarchy(process_id, business_process_name)

        # 1. Group hosts by their template / architectural tier
        tier_hosts: Dict[str, List[Dict[str, Any]]] = {}
        for h in host_inventory:
            tpl = h.get("template", "tpl-webserver")
            tier_info = cls.TEMPLATE_MAPPINGS.get(tpl, {"tier": "General Compute", "rule": RollupRule.WORST_STATE, "quorum_ratio": 0.5})
            tier_name = tier_info["tier"]
            if tier_name not in tier_hosts:
                tier_hosts[tier_name] = []
            tier_hosts[tier_name].append(h)

        # 2. Construct Sub-Service Tier Nodes
        for tier_name, hosts in tier_hosts.items():
            tpl = hosts[0].get("template", "tpl-webserver")
            tier_meta = cls.TEMPLATE_MAPPINGS.get(tpl, {"tier": tier_name, "rule": RollupRule.WORST_STATE, "quorum_ratio": 0.5})
            
            tier_node_id = f"tier_{tier_name.lower().replace(' ', '_')}"
            total_nodes = len(hosts)
            quorum_k = max(1, int(round(total_nodes * tier_meta.get("quorum_ratio", 0.6))))

            tier_node = BPMNode(
                id=tier_node_id,
                name=f"Service Tier: {tier_name}",
                node_type="BUSINESS_SERVICE",
                rollup_rule=tier_meta["rule"],
                quorum_k=quorum_k,
                description=f"Automated group for {total_nodes} nodes in {tier_name}",
                metadata={"template": tpl, "total_instances": total_nodes, "quorum_threshold": quorum_k}
            )
            hierarchy.add_node(tier_node, parent_id=hierarchy.root_id)

            # 3. Add Individual Host Nodes & Service Leaves
            for h in hosts:
                h_name = h.get("hostname", "host-01")
                h_node_id = f"host_{h_name.lower().replace('.', '_')}"
                
                host_node = BPMNode(
                    id=h_node_id,
                    name=f"Host: {h_name}",
                    node_type="HOST_LEAF",
                    state=BPMState.from_str(h.get("state", "OK")),
                    rollup_rule=RollupRule.WORST_STATE,
                    description=f"Host {h_name} (IP: {h.get('ip', '127.0.0.1')})",
                    metadata={"ip": h.get("ip"), "env": h.get("environment", "production")}
                )
                hierarchy.add_node(host_node, parent_id=tier_node_id)

                # Add monitored service leaves if present
                for s in h.get("services", ["ping", "disk", "cpu"]):
                    s_id = f"svc_{h_name}_{s}".lower().replace('.', '_').replace('/', '_')
                    svc_node = BPMNode(
                        id=s_id,
                        name=f"Check: {s} @ {h_name}",
                        node_type="SERVICE_LEAF",
                        state=BPMState.from_str(h.get("service_states", {}).get(s, "OK")),
                        description=f"Monitored service {s} on {h_name}"
                    )
                    hierarchy.add_node(svc_node, parent_id=h_node_id)

        # Initial calculation of full tree
        hierarchy.evaluate_state()
        return hierarchy


if __name__ == "__main__":
    print("================================================================================")
    print("🚀 TESTING BUSINESS PROCESS MODULE (BPM) TREE AUTO-BUILDER")
    print("================================================================================")

    sample_inventory = [
        # Web Tier (3 nodes, Quorum: 2 of 3)
        {"hostname": "web-prod-01.internal", "ip": "10.0.1.11", "template": "tpl-webserver", "state": "OK", "services": ["http", "check_load"]},
        {"hostname": "web-prod-02.internal", "ip": "10.0.1.12", "template": "tpl-webserver", "state": "OK", "services": ["http", "check_load"]},
        {"hostname": "web-prod-03.internal", "ip": "10.0.1.13", "template": "tpl-webserver", "state": "OK", "services": ["http", "check_load"]},
        # MySQL Cluster (3 nodes, Quorum: 2 of 3)
        {"hostname": "db-mysql-primary.internal", "ip": "10.0.2.21", "template": "tpl-mysql-cluster", "state": "OK", "services": ["mysql", "disk /"]},
        {"hostname": "db-mysql-replica-01.internal", "ip": "10.0.2.22", "template": "tpl-mysql-cluster", "state": "OK", "services": ["mysql", "disk /"]},
        {"hostname": "db-mysql-replica-02.internal", "ip": "10.0.2.23", "template": "tpl-mysql-cluster", "state": "OK", "services": ["mysql", "disk /"]},
        # Payment Gateway (1 node, Worst-of-N)
        {"hostname": "payment-api-01.internal", "ip": "10.0.3.31", "template": "tpl-payment-gateway", "state": "OK", "services": ["check_http", "check_ssl_cert"]}
    ]

    bpm = BPMAutoBuilder.build_enterprise_bpm("Global E-Commerce Banking Platform", sample_inventory)
    
    print("\n--- 1. INITIAL HEALTHY BPM TREE ---")
    bpm.print_hierarchy()

    print("\n--- 2. SIMULATING SINGLE WEB NODE FAILURE (1 of 3 Web Down) ---")
    impact1 = bpm.simulate_state_change("host_web-prod-01_internal", BPMState.CRITICAL)
    bpm.print_hierarchy()
    print(f"\nResult: Web Tier Quorum (2 of 3) is still satisfied -> Platform remains OK! (Graceful Degradation)")

    print("\n--- 3. SIMULATING SECOND WEB NODE FAILURE (2 of 3 Web Down) ---")
    impact2 = bpm.simulate_state_change("host_web-prod-02_internal", BPMState.CRITICAL)
    bpm.print_hierarchy()
    print(f"\nResult: Web Tier Quorum breached -> Platform rolls up to WARNING / CRITICAL!")
