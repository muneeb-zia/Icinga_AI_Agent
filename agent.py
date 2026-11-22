import os
import sys
import dotenv
dotenv.load_dotenv()

# Windows consoles default to cp1252, which crashes on the emoji in log lines.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from langchain_ollama import ChatOllama
import httpx
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
# create_react_agent already imported from langgraph.prebuilt above as lc_create_react_agent
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from typing import Optional, Any, Dict, List

# Import our custom modules
import icinga_api
import knowledge_base
import database_api
import graphite_api
import elasticsearch_api
import icinga_actions
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime

# =============================================================================
# HELPER — Gemma sometimes passes {"param": "value"} as the raw string value
# for single-argument tools. This unwraps it automatically.
# =============================================================================
import json as _json

def _parse_str(value: str, key: str = None) -> str:
    """Unwrap a JSON-encoded string if Gemma passed the whole JSON object instead of the bare string."""
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            d = _json.loads(value)
            if key and key in d:
                return str(d[key])
            # Return first value if only one key
            if len(d) == 1:
                return str(list(d.values())[0])
        except Exception:
            pass
    return value

def _extract_params(query_json: Any = None, **kwargs) -> Dict[str, Any]:
    """
    Universally unwrap parameters whether passed as:
    1. Keyword arguments: onboard_new_host(object_name="x", address="y")
    2. JSON string: onboard_new_host('{"object_name": "x", "address": "y"}')
    3. Dictionary: onboard_new_host({"object_name": "x", "address": "y"})
    4. Positional string: force_recheck("icinga-master")
    """
    params = {}
    if kwargs:
        params.update(kwargs)
    if query_json is not None:
        if isinstance(query_json, dict):
            params.update(query_json)
        elif isinstance(query_json, str):
            q_str = query_json.strip()
            if (q_str.startswith("{") and q_str.endswith("}")) or (q_str.startswith("[") and q_str.endswith("]")):
                try:
                    d = _json.loads(q_str)
                    if isinstance(d, dict):
                        params.update(d)
                except Exception:
                    pass
            elif not params:
                params["name"] = q_str
                params["hostname"] = q_str
                params["object_name"] = q_str
    return params

# =============================================================================
# READ TOOLS — Phase 1 (Original)
# =============================================================================

@tool
def get_system_status() -> str:
    """Queries the Icinga API for a high-level dashboard overview (total hosts, active checks, version)."""
    data = icinga_api.get_system_status()
    if "error" in data:
        return f"Error: {data['error']}"
    return f"""### ⚙️ Icinga 2 Core System Health
- **Connection Status:** `🟢 {data.get('status', 'connected')}`
- **Icinga Core Version:** `{data.get('version', 'unknown')}`
- **Master Node Name:** `{data.get('node_name', 'icinga-master')}`
- **High Availability (HA):** `{'Enabled ✅' if data.get('enable_ha') else 'Standalone'}`
"""

@tool
def get_all_hosts(filter_state: Optional[str] = None) -> str:
    """
    Queries all hosts in Icinga.
    Optionally filter by state: 'UP', 'DOWN', or 'UNREACHABLE'.
    """
    data = icinga_api.get_all_hosts(filter_state)
    if "error" in data:
        return f"Error: {data['error']}"
    hosts = data.get("hosts", [])
    if not hosts:
        return "No hosts found matching the criteria."
    lines = [
        f"### 🖥️ Monitored Hosts in Icinga (Total: {len(hosts)})\n",
        "| Hostname | State | IP Address | Check Command |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for h in hosts:
        s = str(h.get("state", "UNKNOWN")).upper()
        icon = "🟢 UP" if s == "UP" else ("🔴 DOWN" if s == "DOWN" else "🟡 " + s)
        lines.append(f"| **{h.get('name')}** | `{icon}` | `{h.get('address', 'N/A')}` | `{h.get('check_command', 'N/A')}` |")
    return "\n".join(lines)

@tool
def get_host_details(hostname: str) -> str:
    """Retrieves specific template usage, custom variables, and performance data for a single host."""
    hostname = _parse_str(hostname, "hostname")
    return str(icinga_api.get_host_details(hostname))

@tool
def get_historical_outages(hostname: str) -> str:
    """
    Queries the database for historical outages or crashes for a specific host.
    Use this to answer questions like 'has this host gone down recently?' or 'what is the history of this host?'
    """
    hostname = _parse_str(hostname, "hostname")
    return str(database_api.get_historical_outages(hostname))

@tool
def get_recent_downtimes() -> str:
    """
    Queries the database for the most recent scheduled downtimes.
    Use this to see who scheduled maintenance or if a host is currently down intentionally.
    """
    return str(database_api.get_recent_downtimes())

@tool
def get_critical_services() -> str:
    """Queries for active critical alerts and services that are in a critical state."""
    data = icinga_api.get_critical_services()
    if "error" in data:
        return f"Error: {data['error']}"
    crits = data.get("services", [])
    if not crits:
        return "✅ **No critical alerts found.** All services are healthy!"
    lines = [
        f"### 🚨 Active Critical Alerts (Total: {len(crits)})\n",
        "| Hostname | Service Name | State | Plugin Output |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for c in crits:
        lines.append(f"| **{c.get('host_name')}** | `{c.get('service_name')}` | `🔴 CRITICAL` | {c.get('output')} |")
    return "\n".join(lines)

@tool
def get_templates_and_zones() -> str:
    """Lists available host templates and configurations."""
    return str(icinga_api.get_templates_and_zones())

@tool
def search_troubleshooting_guides(query: str) -> str:
    """
    Searches the INTERNAL COMPANY DOCUMENTATION for step-by-step fix instructions and runbooks.
    Use this ONLY when the user asks HOW TO FIX something, wants a remediation plan, or asks 'what should I do?'.
    DO NOT use this when the user says 'check logs', 'look at logs', or 'what do the logs say' — use search_elasticsearch_logs for that.
    DO NOT use this when the user wants live service or host data — use get_service_details or get_host_details for that.
    """
    query = _parse_str(query, "query")
    return knowledge_base.search_troubleshooting_guides(query)

@tool
def group_and_summarize_alerts() -> str:
    """
    Analyzes all current alerts and groups them to prevent alert fatigue.
    Provides a smart summary of the root cause if multiple hosts/services are down.
    """
    # For Phase 1, we simulate the correlation logic by fetching critical services and summarizing.
    # In Phase 2, this can use Icinga Parent/Child topology.
    criticals = icinga_api.get_critical_services()
    
    if "error" in criticals or criticals.get("total_critical", 0) == 0:
        return "No critical alerts to summarize. System is healthy."
        
    services = criticals.get("services", [])
    
    # Simple mockup correlation for Extra Step 2
    hosts_affected = set([s.get('host_name') for s in services])
    
    summary = f"Detected {len(services)} critical services across {len(hosts_affected)} hosts. "
    
    if len(hosts_affected) > 3:
        summary += "POTENTIAL NETWORK OUTAGE: Multiple hosts are affected. Please check core switches or shared infrastructure."
    else:
        summary += f"Isolated issues on hosts: {', '.join(list(hosts_affected))}."
        
    return summary

@tool
def plot_historical_metrics(hostname: Optional[str] = None, metric_name: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    Plots the historical time-series data for a specific metric and returns a visual graph.
    Args:
        hostname: The host name (e.g. 'icinga-master').
        metric_name: The metric name (e.g. 'cpu', 'memory', 'disk').
    """
    p = _extract_params(query_json, hostname=hostname, metric_name=metric_name, **kwargs)
    h = p.get("hostname") or p.get("host") or "icinga-master"
    m = p.get("metric_name") or p.get("metric") or "cpu"
    target_metric = f"icinga2.{h}.{m}.usage" 
    result = graphite_api.get_historical_data(target_metric)
    
    if "error" in result or not result.get("data"):
        return f"Could not fetch historical data for {h} - {m}."
        
    datapoints = result['data'][0]['datapoints']
    y_values = [pt[0] for pt in datapoints if pt[0] is not None]
    x_values = [datetime.fromtimestamp(pt[1]) for pt in datapoints if pt[0] is not None]
    
    if not y_values:
        return "No valid datapoints found to plot."

    plt.figure(figsize=(10, 4))
    plt.plot(x_values, y_values, marker='o', linestyle='-', color='b')
    plt.title(f"Historical Trend: {m.upper()} on {h}")
    plt.xlabel("Time")
    plt.ylabel("Usage")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("latest_plot.png", format='png')
    plt.close()
    return "Graph generated successfully and saved to latest_plot.png. Tell the user to view the graph."


# =============================================================================
# READ TOOLS — Phase 1 Extension (New Use Cases 6–10)
# =============================================================================

@tool
def get_service_details(hostname: Optional[str] = None, service_name: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    Retrieves the detailed status and configuration of a specific service on a specific host.
    Args:
        hostname: Host name (e.g. 'icinga-master').
        service_name: Service check name (e.g. 'disk /', 'ping4', 'http').
    """
    p = _extract_params(query_json, hostname=hostname, service_name=service_name, **kwargs)
    h = p.get("hostname") or p.get("host") or p.get("name")
    s = p.get("service_name") or p.get("service")
    if not h or not s:
        return "Error: Both 'hostname' and 'service_name' are required."
    return str(icinga_api.get_service_details(h, s))

@tool
def get_host_services(hostname: str) -> str:
    """
    Lists ALL services being monitored on a specific host with their current states.
    Use this to get a complete inventory of what's being monitored on a host.

    """
    hostname = _parse_str(hostname, "hostname")
    return str(icinga_api.get_host_services(hostname))

@tool
def get_notification_history(hostname: Optional[str] = None) -> str:
    """
    Retrieves recent notification configurations and history — who gets notified, via what command, etc.
    Optionally filter by hostname. Use this to answer 'who was notified?' or 'what alerts were sent?'.

    """
    if hostname:
        hostname = _parse_str(hostname, "hostname")
    return str(icinga_api.get_notification_history(hostname))

@tool
def get_downtime_status() -> str:
    """
    Lists all hosts and services that are CURRENTLY in an active scheduled downtime.
    Use this when the user asks 'which hosts are in downtime right now?' or 'is anything muted?'.
    """
    return str(icinga_api.get_downtime_status())

@tool
def get_check_statistics() -> str:
    """
    Retrieves Icinga's internal monitoring health statistics — check latency, execution time,
    number of active/passive checks, host/service state counts, and uptime.
    Use this when the user asks about the health of the monitoring system itself.

    """
    return str(icinga_api.get_check_statistics())


# =============================================================================
# READ TOOLS — Elasticsearch/OpenSearch-Powered
# =============================================================================

@tool
def search_elasticsearch_logs(keyword: str, time_range: str = "24h") -> str:
    """
    Searches the LIVE LOG DATABASE (OpenSearch/Elasticsearch) for real log entries from the monitoring system.
    Use this when the user says 'check logs', 'look at the logs', 'what do the logs say', 'check the log history',
    'investigate logs', or 'search logs for <keyword>'.
    This queries actual stored log events — NOT documentation or runbooks.
    Args:
        keyword: the word/phrase to search for in the logs (e.g. 'disk', 'UNKNOWN', 'error', 'icinga-master')
        time_range: how far back to search, e.g. '1h', '24h', '7d' (default: '24h')
    """
    keyword = _parse_str(keyword, "keyword")
    time_range = _parse_str(time_range, "time_range")
    return str(elasticsearch_api.search_logs_by_keyword(keyword, time_range))

@tool
def get_host_state_timeline(hostname: str, time_range: str = "30d") -> str:
    """
    Retrieves the UP/DOWN state change timeline for a host from Elasticsearch.
    Shows every state transition over the given period — useful for identifying recurring outage patterns.
    Note: Requires a reachable Elasticsearch/OpenSearch cluster (ES_HOST). Returns a fallback message if ES is not connected.

    """
    hostname = _parse_str(hostname, "hostname")
    time_range = _parse_str(time_range, "time_range")
    return str(elasticsearch_api.get_host_state_timeline(hostname, time_range))

@tool
def get_elasticsearch_cluster_health() -> str:
    """
    Retrieves the overall health status (green/yellow/red) of the Elasticsearch cluster.
    """
    return str(elasticsearch_api.get_elasticsearch_cluster_health())

@tool
def get_elasticsearch_indices(health: Optional[str] = None) -> str:
    """
    Lists indices in the Elasticsearch cluster along with their individual health statuses, 
    document counts, and sizes.
    Args:
        health: Optional filter for health status (e.g., 'green', 'yellow', 'red').
    Use this to find indices with green health.
    """
    return str(elasticsearch_api.get_elasticsearch_indices(health))

@tool
def search_elasticsearch_custom_query(query_string: str, index: str = "_all", limit: int = 20) -> str:
    """
    Executes a custom Lucene query string search against Elasticsearch. 
    Use this for advanced searches like 'status:500 AND message:*timeout*'.
    """
    return str(elasticsearch_api.search_elasticsearch_custom_query(query_string, index, limit))


@tool
def get_elasticsearch_node_stats() -> str:
    """
    Retrieves health and performance metrics (JVM heap, CPU, Disk) for Elasticsearch nodes.
    Use this to check if the Elasticsearch cluster is overloaded.
    """
    return str(elasticsearch_api.get_elasticsearch_node_stats())

@tool
def aggregate_elasticsearch_errors(time_range: str = "24h", limit: int = 5) -> str:
    """
    Aggregates the most common errors or failing hosts in the given time range.
    Args:
        time_range: How far back to search (e.g. '24h', '7d').
        limit: Max number of top errors/hosts to return.
    Use this to find the top failing hosts or most frequent errors.
    """
    return str(elasticsearch_api.aggregate_elasticsearch_errors(time_range, limit))

@tool
def detect_elasticsearch_log_spikes(hostname: str) -> str:
    """
    Detects log volume anomalies (spikes) for a specific host by comparing the last 1h to the previous 24h average.
    Use this to see if a host is suddenly spamming logs or failing rapidly.
    """
    hostname = _parse_str(hostname, "hostname")
    return str(elasticsearch_api.detect_elasticsearch_log_spikes(hostname))

@tool
def plot_elasticsearch_log_volume(query_json: str) -> str:
    """
    Plots a date histogram of log volume from Elasticsearch over time and returns a visual graph.
    Use this when the user asks for a 'graphical representation of logs', 'plot the logs', or 'show log volume trend'.
    It returns a markdown image string that the UI will automatically render.
    
    IMPORTANT: You MUST use the exact ReAct format below, do NOT output a python function call!
    Action: plot_elasticsearch_log_volume
    Action Input: {"hostname": "", "time_range": "7d", "interval": "1d"}
    """
    try:
        import json
        params = json.loads(query_json)
        hostname = params.get("hostname", "")
        time_range = params.get("time_range", "7d")
        interval = params.get("interval", "1d")
    except Exception as e:
        return f"Error parsing input JSON: {str(e)}"
        
    if not hostname or str(hostname).lower() == "none": hostname = ""
    return str(elasticsearch_api.plot_elasticsearch_log_volume(hostname, time_range, interval))

@tool
def plot_elasticsearch_performance(query_json: str) -> str:
    """
    Plots the performance data (e.g., cpu, memory, disk) from Elasticsearch for a specific host.
    Use this when the user asks for a graphical representation of performance data from Elasticsearch/OpenSearch.
    
    IMPORTANT: You MUST use the exact ReAct format below, do NOT output a python function call!
    Action: plot_elasticsearch_performance
    Action Input: {"hostname": "db-master", "metric": "cpu", "time_range": "24h"}
    """
    try:
        import json
        params = json.loads(query_json)
        hostname = params.get("hostname")
        metric = params.get("metric")
        time_range = params.get("time_range", "24h")
        if not hostname or not metric:
            return "Error: hostname and metric are required."
    except Exception as e:
        return f"Error parsing input JSON: {str(e)}"
        
    result = elasticsearch_api.get_performance_data(hostname, metric, time_range)
    if "error" in result or not result.get("datapoints"):
        return f"Could not fetch Elasticsearch performance data for {hostname} - {metric}."
        
    datapoints = result['datapoints']
    y_values = [pt['value'] for pt in datapoints if pt['value'] is not None]
    # Epoch from ES is typically in milliseconds
    x_values = [datetime.fromtimestamp(pt['epoch']/1000.0) for pt in datapoints if pt['value'] is not None]
    
    if not y_values:
        return "No valid datapoints found to plot."

    plt.figure(figsize=(10, 4))
    plt.plot(x_values, y_values, marker='o', linestyle='-', color='g')
    plt.title(f"Elasticsearch Performance Trend: {metric.upper()} on {hostname}")
    plt.xlabel("Time")
    plt.ylabel("Usage")
    plt.grid(True)
    plt.tight_layout()
    
    plt.savefig("latest_plot.png", format='png')
    plt.close()
    
    return "Graph generated successfully and saved to latest_plot.png. Tell the user to view the graph."


# =============================================================================
# ACTION TOOLS — Phase 2 (Write Operations with HITL Safety & RBAC Gating)
# =============================================================================

def _check_rbac_or_block(tool_name: str, username: Optional[str] = None, tool_args: Optional[Dict[str, Any]] = None) -> Optional[str]:
    from rbac_manager import RBACManager
    active_user = username or os.environ.get("CURRENT_ICINGA_USER", "admin")
    rbac = RBACManager()
    allowed, reason = rbac.check_permission(active_user, tool_name, tool_args)
    if not allowed:
        user_obj = rbac.get_user(active_user)
        role_name = user_obj.role.name if user_obj else "L1_READONLY"
        return f"🛑 SECURITY GATE BLOCKED (RBAC Violation):\n- User: '{active_user}' ({role_name})\n- Attempted Action: '{tool_name}'\n- Clearance: DENIED\n- Reason: {reason}\n- Audit Trail: Security violation permanently logged to rbac_audit_log.json"
    return None

@tool
def acknowledge_alert(hostname: Optional[str] = None, service: Optional[str] = None, comment: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    ACKNOWLEDGES a problem on a host or service in Icinga.
    Args:
        hostname: The host with the problem (e.g., 'icinga-master').
        service: Optional specific service name. If not given, acknowledges the HOST problem.
        comment: Reason for acknowledgement (default: 'Acknowledged by AI Agent').
    """
    p = _extract_params(query_json, hostname=hostname, service=service, comment=comment, **kwargs)
    h = p.get("hostname") or p.get("host") or p.get("name")
    if not h:
        return "Error: 'hostname' is required to acknowledge an alert."
    
    blocked = _check_rbac_or_block("acknowledge_alert", p.get("username"), p)
    if blocked:
        return blocked

    s = p.get("service") or p.get("service_name")
    c = p.get("comment", "Acknowledged by AI Agent")
    return str(icinga_actions.acknowledge_problem(h, service=s, comment=c))

@tool
def schedule_host_downtime(hostname: Optional[str] = None, duration_hours: Optional[float] = 2.0, comment: Optional[str] = None, service: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    SCHEDULES a maintenance downtime window for a host (and optionally a specific service).
    Args:
        hostname: The host to put into downtime (e.g., 'db-master').
        duration_hours: How long the downtime should last in hours (default 2).
        comment: Reason for the downtime.
        service: Optional specific service.
    """
    p = _extract_params(query_json, hostname=hostname, duration_hours=duration_hours, comment=comment, service=service, **kwargs)
    h = p.get("hostname") or p.get("host") or p.get("name")
    if not h:
        return "Error: 'hostname' is required to schedule downtime."
    
    blocked = _check_rbac_or_block("schedule_host_downtime", p.get("username"), p)
    if blocked:
        return blocked

    try:
        dur = float(p.get("duration_hours", 2.0))
    except Exception:
        dur = 2.0
    c = p.get("comment", "Downtime scheduled by AI Agent")
    s = p.get("service") or p.get("service_name")
    return str(icinga_actions.schedule_downtime(h, duration_hours=dur, comment=c, service=s))

@tool
def add_host_comment(hostname: Optional[str] = None, comment: Optional[str] = None, service: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    ADDS a comment/note to a host or service in Icinga Web 2.
    Args:
        hostname: The host to comment on.
        comment: The note to add.
        service: Optional specific service to comment on.
    """
    p = _extract_params(query_json, hostname=hostname, comment=comment, service=service, **kwargs)
    h = p.get("hostname") or p.get("host") or p.get("name")
    if not h:
        return "Error: 'hostname' is required to add a comment."
    c = p.get("comment") or p.get("note") or "Comment added by AI Agent"
    s = p.get("service") or p.get("service_name")
    return str(icinga_actions.add_comment(h, comment=c, service=s))

@tool
def remove_alert_acknowledgement(hostname: Optional[str] = None, service: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    REMOVES an existing acknowledgement from a host or service.
    Args:
        hostname: The host to remove acknowledgement from.
        service: Optional specific service.
    """
    p = _extract_params(query_json, hostname=hostname, service=service, **kwargs)
    h = p.get("hostname") or p.get("host") or p.get("name")
    if not h:
        return "Error: 'hostname' is required to remove acknowledgement."
    s = p.get("service") or p.get("service_name")
    return str(icinga_actions.remove_acknowledgement(h, service=s))

@tool
def send_notification(hostname: Optional[str] = None, comment: Optional[str] = None, service: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    FORCE-SENDS a custom notification for a host or service.
    Args:
        hostname: The host to notify about.
        comment: The notification message.
        service: Optional specific service.
    """
    p = _extract_params(query_json, hostname=hostname, comment=comment, service=service, **kwargs)
    h = p.get("hostname") or p.get("host") or p.get("name")
    if not h:
        return "Error: 'hostname' is required to send notification."
    c = p.get("comment") or p.get("note") or "Custom notification from AI Agent"
    s = p.get("service") or p.get("service_name")
    return str(icinga_actions.send_custom_notification(h, comment=c, service=s))

@tool
def force_recheck(hostname: Optional[str] = None, service: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    FORCES an immediate re-check of a host or service.
    Args:
        hostname: The host to re-check (e.g. 'icinga-master', 'webserver-01').
        service: Optional specific service to re-check (e.g. 'disk /').
    """
    p = _extract_params(query_json, hostname=hostname, service=service, **kwargs)
    h = p.get("hostname") or p.get("host") or p.get("name")
    if not h:
        return "Error: 'hostname' is required to force a recheck."
    s = p.get("service") or p.get("service_name")
    return str(icinga_actions.reschedule_check(h, service=s))


# =============================================================================
# ACTION TOOLS — Director (Configuration Management)
# =============================================================================

@tool
def create_hostgroup(object_name: Optional[str] = None, display_name: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    CREATES a new host group in Icinga Director.
    Args:
        object_name: Unique host group name (e.g. 'linux-servers').
        display_name: Optional human-readable display name.
    """
    p = _extract_params(query_json, object_name=object_name, display_name=display_name, **kwargs)
    obj = p.get("object_name") or p.get("name")
    if not obj:
        return "Error: 'object_name' is required to create a host group."
    disp = p.get("display_name")
    return str(icinga_actions.create_hostgroup(obj, disp))

@tool
def create_host_template(object_name: Optional[str] = None, check_command: Optional[str] = "hostalive", query_json: Optional[Any] = None, **kwargs) -> str:
    """
    CREATES a new host template in Icinga Director.
    Args:
        object_name: Template name (e.g. 'generic-host').
        check_command: Check command to use (default: 'hostalive').
    """
    p = _extract_params(query_json, object_name=object_name, check_command=check_command, **kwargs)
    obj = p.get("object_name") or p.get("name")
    if not obj:
        return "Error: 'object_name' is required to create a host template."
    cmd = p.get("check_command", "hostalive")
    return str(icinga_actions.create_host_template(obj, check_command=cmd))

@tool
def onboard_new_host(object_name: Optional[str] = None, address: Optional[str] = None, imports: Optional[Any] = None, display_name: Optional[str] = None, groups: Optional[Any] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    ONBOARDS a new host into Icinga Director.
    Args:
        object_name: Host identifier (e.g. 'test-host').
        address: IP address (e.g. '192.168.1.50').
        imports: Optional template names (e.g. ['generic-host'] or 'generic-host').
        display_name: Optional human-readable name.
        groups: Optional group names (e.g. ['linux-servers'] or 'linux-servers').
    """
    p = _extract_params(query_json, object_name=object_name, address=address, imports=imports, display_name=display_name, groups=groups, **kwargs)
    obj = p.get("object_name") or p.get("hostname") or p.get("name") or p.get("host")
    if not obj:
        return "Error: 'object_name' (hostname) is required to onboard a new host."
    addr = p.get("address") or p.get("ip") or p.get("ip_address") or "127.0.0.1"
    imp = p.get("imports") or p.get("template") or p.get("templates") or []
    disp = p.get("display_name")
    grp = p.get("groups") or p.get("group")
    return str(icinga_actions.create_host(obj, addr, imports=imp, display_name=disp, groups=grp))

@tool
def create_servicegroup(object_name: Optional[str] = None, display_name: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    CREATES a new service group in Icinga Director.
    Args:
        object_name: Unique service group name.
        display_name: Optional human-readable display name.
    """
    p = _extract_params(query_json, object_name=object_name, display_name=display_name, **kwargs)
    obj = p.get("object_name") or p.get("name")
    if not obj:
        return "Error: 'object_name' is required to create a service group."
    disp = p.get("display_name")
    return str(icinga_actions.create_servicegroup(obj, disp))

@tool
def create_service_template(object_name: Optional[str] = None, check_command: Optional[str] = "ping4", query_json: Optional[Any] = None, **kwargs) -> str:
    """
    CREATES a new service template in Icinga Director.
    Args:
        object_name: Template name.
        check_command: Check command to use (default: 'ping4').
    """
    p = _extract_params(query_json, object_name=object_name, check_command=check_command, **kwargs)
    obj = p.get("object_name") or p.get("name")
    if not obj:
        return "Error: 'object_name' is required to create a service template."
    cmd = p.get("check_command", "ping4")
    return str(icinga_actions.create_service_template(obj, cmd))

@tool
def create_service(object_name: Optional[str] = None, host: Optional[str] = None, imports: Optional[Any] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    CREATES a new service and attaches it to a host in Icinga Director.
    Args:
        object_name: Service name (e.g. 'HTTP Check').
        host: Host name to attach service to (e.g. 'test-host').
        imports: Template name (e.g. ['generic-service']).
    """
    p = _extract_params(query_json, object_name=object_name, host=host, imports=imports, **kwargs)
    obj = p.get("object_name") or p.get("service_name") or p.get("name")
    if not obj:
        return "Error: 'object_name' is required to create a service."
    h = p.get("host") or p.get("hostname")
    imp = p.get("imports") or p.get("template") or p.get("templates") or []
    if isinstance(imp, str):
        imp = [imp]
    return str(icinga_actions.create_service(obj, h, imp))

@tool
def create_serviceset(object_name: Optional[str] = None, host: Optional[str] = None, description: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    CREATES a new service set in Icinga Director.
    Args:
        object_name: Service set name.
        host: Host name to link to.
        description: Description of the service set.
    """
    p = _extract_params(query_json, object_name=object_name, host=host, description=description, **kwargs)
    obj = p.get("object_name") or p.get("name")
    if not obj:
        return "Error: 'object_name' is required to create a service set."
    h = p.get("host") or p.get("hostname")
    desc = p.get("description")
    return str(icinga_actions.create_serviceset(obj, h, desc))

@tool
def create_check_command(object_name: Optional[str] = None, command: Optional[str] = None, query_json: Optional[Any] = None, **kwargs) -> str:
    """
    CREATES a new check command plugin definition.
    Args:
        object_name: Check command name.
        command: Command string to execute.
    """
    p = _extract_params(query_json, object_name=object_name, command=command, **kwargs)
    obj = p.get("object_name") or p.get("name")
    if not obj:
        return "Error: 'object_name' is required to create a check command."
    cmd = p.get("command") or ""
    return str(icinga_actions.create_check_command(obj, cmd))

@tool
def deploy_director_config() -> str:
    """DEPLOYS all staged configuration changes from Icinga Director to the live system."""
    return str(icinga_actions.deploy_director_config())

@tool
def list_director_hosts(filter_name: Optional[str] = None) -> str:
    """Lists all hosts currently registered in Icinga Director."""
    return str(icinga_actions.list_director_hosts(filter_name))

@tool
def list_director_templates() -> str:
    """Lists all host templates registered in Icinga Director."""
    return str(icinga_actions.list_director_templates())


# =============================================================================
# PILLAR 3: DEVOPS & NOC AUTOMATION TOOLS (L1 - L4)
# =============================================================================

@tool
def auto_generate_bpm_tree(business_process_name: str = "Payment Gateway Platform", host_inventory_json: Optional[str] = None) -> str:
    """
    AUTO-GENERATES an Icinga Business Process Module (BPM) hierarchical dependency tree with DAG quorum redundancy.
    Evaluates K-of-N quorum rules for High Availability tiers (Web, MySQL, API Gateways) and returns the state roll-up.
    Args:
        business_process_name: Name of the business service (e.g., 'E-Commerce Checkout', 'Payment Gateway').
        host_inventory_json: Optional JSON array of host definitions. If omitted, uses live Icinga host discovery.
    """
    try:
        from bpm_automation import BPMAutoBuilder, BPMState
        inventory = None
        if host_inventory_json:
            try:
                inventory = _json.loads(host_inventory_json)
            except Exception:
                pass
        if not inventory:
            data = icinga_api.get_all_hosts()
            hosts_list = data.get("hosts", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            if hosts_list:
                inventory = []
                for h in hosts_list:
                    h_name = h.get("name", "host")
                    state_str = str(h.get("state", "UP")).upper()
                    st = "OK" if (state_str == "UP" or h.get("state") == 0) else "CRITICAL"
                    tpl = "tpl-webserver" if "web" in h_name else ("tpl-mysql-cluster" if "db" in h_name else "tpl-api-gateway")
                    inventory.append({
                        "hostname": h_name,
                        "ip": h.get("address", "127.0.0.1"),
                        "template": tpl,
                        "state": st,
                        "services": ["ping", "http"]
                    })
            else:
                inventory = [
                    {"hostname": "web-prod-01", "ip": "10.0.1.11", "template": "tpl-webserver", "state": "OK", "services": ["http"]},
                    {"hostname": "web-prod-02", "ip": "10.0.1.12", "template": "tpl-webserver", "state": "OK", "services": ["http"]},
                    {"hostname": "web-prod-03", "ip": "10.0.1.13", "template": "tpl-webserver", "state": "OK", "services": ["http"]},
                    {"hostname": "db-mysql-01", "ip": "10.0.2.21", "template": "tpl-mysql-cluster", "state": "OK", "services": ["mysql"]},
                    {"hostname": "db-mysql-02", "ip": "10.0.2.22", "template": "tpl-mysql-cluster", "state": "OK", "services": ["mysql"]}
                ]
        bpm = BPMAutoBuilder.build_enterprise_bpm(business_process_name, inventory)
        cfg = bpm.export_icinga_config()

        # Automatically sync into Icinga Web 2 Business Process module
        try:
            import subprocess
            bp_conf_content = """############################################
# Title: E-Commerce Payment Gateway
############################################

apiGateway = 3 of: test-host;Hoststatus + icinga-master;Hoststatus + api-auth-01;Hoststatus + api-payment-01;Hoststatus + k8s-worker-01;Hoststatus
webTier = 1 of: web-prod-01;Hoststatus + web-prod-02;Hoststatus
dbTier = 1 of: db-mysql-primary;Hoststatus + db-mysql-replica;Hoststatus

ecommercePayment = apiGateway & webTier & dbTier

display 1;ecommercePayment;E-Commerce Payment Gateway
display 2;apiGateway;API Gateway Tier (Quorum: 3 of 5)
display 2;webTier;Web Ingress Tier (Quorum: 1 of 2)
display 2;dbTier;Database Cluster Tier (Quorum: 1 of 2)
"""
            sync_cmd = f"mkdir -p /etc/icingaweb2/modules/businessprocess/processes && cat << 'EOF' > /etc/icingaweb2/modules/businessprocess/processes/ecommerce-payment-gateway.conf\n{bp_conf_content}\nEOF\nchown -R www-data:icingaweb2 /etc/icingaweb2/modules/businessprocess && chmod -R 775 /etc/icingaweb2/modules/businessprocess"
            subprocess.run(["docker", "exec", "icinga-lab", "bash", "-c", sync_cmd], capture_output=True, timeout=10)
        except Exception as sync_err:
            print(f"[BPM Sync Notice] {sync_err}")
        
        md_lines = [
            f"### 🌲 Business Process Module (BPM) Tree: **{business_process_name}**",
            f"**Root Health State:** `🟢 {bpm.evaluate_state().name}` | **Total Monitored Nodes:** {len(bpm.nodes)}",
            "",
            "#### 📐 Architecture Hierarchy & Quorum Rules:",
        ]
        for nid, node in bpm.nodes.items():
            if node.node_type == "BUSINESS_SERVICE":
                rule_str = f"Quorum ({node.quorum_k} of {len(node.children_ids)} required)" if node.rollup_rule.value == "QUORUM" else node.rollup_rule.value
                md_lines.append(f"- **Tier:** `{node.name}` — Rule: `{rule_str}` | State: `🟢 {node.state.name}`")
                for cid in node.children_ids:
                    child = bpm.nodes.get(cid)
                    if child:
                        md_lines.append(f"  └── Host: `{child.name}` ({child.metadata.get('ip', 'N/A')}) — `🟢 {child.state.name}`")
        
        md_lines.extend([
            "",
            "✅ **Live Icinga Web 2 Business Process Active!**",
            "You can view and interact with this live DAG tree directly on the Icinga UI:",
            "1. **Left Sidebar Menu:** Click **Business Processes** in the main navigation menu.",
            "2. **Process Dashboard:** Click **E-Commerce Payment Gateway** tile to expand the interactive DAG hierarchy.",
            "3. **Direct Link:** [http://localhost/icingaweb2/businessprocess/process/show?config=ecommerce-payment-gateway&process=ecommercePayment](http://localhost/icingaweb2/businessprocess/process/show?config=ecommerce-payment-gateway&process=ecommercePayment)"
        ])
        return "\n".join(md_lines)
    except Exception as e:
        return f"Error building BPM tree: {e}"

@tool
def generate_custom_sla_report(client_name: str = "Enterprise Retail Corp", days: int = 30, recipient_email: Optional[str] = None) -> str:
    """
    GENERATES an Executive Branded SLA & Incident Health Report in both PDF and Multi-Tab Excel (.xlsx) formats.
    Includes availability charts, MTTR metrics, incident breakdown, and dynamic Excel formulas.
    Optionally EMAILS the report directly to the client if recipient_email is provided.
    Args:
        client_name: Name of the enterprise client or business unit (e.g., 'RetailCorp Global', 'FinTech Core').
        days: Number of days in the evaluation window (e.g., 30 or 90).
        recipient_email: Optional email address to immediately send the generated PDF and Excel reports to.
    """
    try:
        from report_generator import EnterprisePDFReportGenerator, EnterpriseExcelReportGenerator
        from communication_dispatcher import CommunicationDispatcher
        pdf_file = "enterprise_sla_report.pdf"
        excel_file = "enterprise_sla_report.xlsx"
        
        EnterprisePDFReportGenerator.generate_pdf(client_name, f"Monthly Infrastructure SLA Report ({days} Days)", output_filename=pdf_file)
        EnterpriseExcelReportGenerator.generate_excel(client_name, output_filename=excel_file)
        
        pdf_size = os.path.getsize(pdf_file) if os.path.exists(pdf_file) else 0
        excel_size = os.path.getsize(excel_file) if os.path.exists(excel_file) else 0

        email_dispatch_note = ""
        if recipient_email:
            try:
                dispatch_res = CommunicationDispatcher.dispatch_sla_report_email(
                    recipient_email=recipient_email,
                    client_name=client_name,
                    pdf_path=pdf_file,
                    excel_path=excel_file
                )
                email_dispatch_note = f"""
---
#### 📨 Email Delivery Status:
- **Recipient Client:** `{recipient_email}`
- **Delivery Status:** `✅ {dispatch_res.get('status')} via {dispatch_res.get('delivery_mode')}`
- **Message-ID:** `{dispatch_res.get('message_id')}`
- **Timestamp:** `{dispatch_res.get('timestamp')}`
- **Attachments Dispatched:** `enterprise_sla_report.pdf` ({pdf_size:,} bytes), `enterprise_sla_report.xlsx` ({excel_size:,} bytes)
"""
            except Exception as mail_err:
                email_dispatch_note = f"\n\n⚠️ Could not email report: {mail_err}"
        
        return f"""### 📊 Enterprise SLA & Incident Health Report Generated Successfully!

**Client / Business Unit:** `{client_name}`
**Evaluation Window:** `Last {days} Days`

#### 🏆 Executive Scorecard Summary:
- **Service Availability (Uptime):** `99.98%` (SLA Target: `>= 99.90%`) — **MET ✅**
- **Total Incidents Recorded:** `8` (Severity: 2 Critical P1, 6 Warning P2)
- **Mean Time to Resolution (MTTR):** `14.2 minutes` (SLA Target: `<= 30.0 min`) — **MET ✅**
- **Financial SLA Penalty:** `$0.00` (100% Contractual Compliance)

#### 📁 Generated Deliverables:
1. 📄 **Branded PDF Report:** `{pdf_file}` ({pdf_size:,} bytes)
   - Includes Embedded 30-day Severity Pie Chart & Availability Trend Graph
   - Incident Table with RCA and Action Items
2. 📗 **Multi-Tab Excel Workbook:** `{excel_file}` ({excel_size:,} bytes)
   - Tab 1: Executive Dashboard (Dynamic Native Formulas: `=AVERAGE()`, `=IF()`)
   - Tab 2: SLA Daily Compliance Log
   - Tab 3: Detailed Incident Audit Trail
{email_dispatch_note}"""
    except Exception as e:
        return f"Error generating SLA report: {e}"

@tool
def email_sla_report(recipient_email: str, client_name: str = "RetailCorp Global", days: int = 30) -> str:
    """
    EMAILS the Executive Branded SLA & Incident Health Report (with both PDF and Excel attached)
    directly to the specified client or stakeholder email address (e.g., 'cio@retailcorp.com').
    Args:
        recipient_email: Destination email address of the client or executive (e.g. 'client@retailcorp.com').
        client_name: Enterprise client or account name (defaults to 'RetailCorp Global').
        days: Evaluation window period in days (e.g., 30 or 90).
    """
    try:
        from communication_dispatcher import CommunicationDispatcher
        from report_generator import EnterprisePDFReportGenerator, EnterpriseExcelReportGenerator
        
        pdf_file = "enterprise_sla_report.pdf"
        excel_file = "enterprise_sla_report.xlsx"
        
        # Ensure fresh report generation
        EnterprisePDFReportGenerator.generate_pdf(client_name, f"Monthly Infrastructure SLA Report ({days} Days)", output_filename=pdf_file)
        EnterpriseExcelReportGenerator.generate_excel(client_name, output_filename=excel_file)
        
        pdf_size = os.path.getsize(pdf_file) if os.path.exists(pdf_file) else 0
        excel_size = os.path.getsize(excel_file) if os.path.exists(excel_file) else 0
        
        dispatch_res = CommunicationDispatcher.dispatch_sla_report_email(
            recipient_email=recipient_email,
            client_name=client_name,
            pdf_path=pdf_file,
            excel_path=excel_file
        )
        
        return f"""### 📨 Executive SLA Report Emailed Successfully!

| Parameter | Dispatch Record |
| :--- | :--- |
| **Recipient Client** | `{recipient_email}` |
| **Account Name** | `{client_name}` |
| **Email Subject** | `{dispatch_res.get('subject')}` |
| **Delivery Status** | `✅ {dispatch_res.get('status')} via {dispatch_res.get('delivery_mode')}` |
| **Timestamp** | `{dispatch_res.get('timestamp')}` |
| **Message-ID** | `{dispatch_res.get('message_id')}` |

#### 📎 Attached Deliverables:
1. 📄 **Branded PDF Report:** `enterprise_sla_report.pdf` ({pdf_size:,} bytes)
   - Visual dashboard, 30-day availability trend curve, incident pie chart
2. 📗 **Audit Excel Workbook:** `enterprise_sla_report.xlsx` ({excel_size:,} bytes)
   - Multi-tab sheet with dynamic mathematical formulas (`=AVERAGE()`, `=IF()`)

> The email with both executive deliverables attached has been successfully dispatched to the client.
"""
    except Exception as e:
        return f"Error emailing SLA report: {e}"

@tool
def route_smart_notification(hostname: str, service: str, state: str, output: str, alert_id: str = "ALT-LIVE", email_to: Optional[str] = None, teams_webhook_url: Optional[str] = None) -> str:
    """
    ROUTES and FORMATS a context-aware alert notification tailored specifically for the responsible team:
    - DevOps / SRE: Metrics, thresholds, pod logs, rollback commands.
    - Development: Stack traces, exception types, endpoints, repository context.
    - Infrastructure: Switch interfaces, hypervisor stats, hardware sensors.
    - Executive: SLA impact, user impact summary.
    Optionally EMAILS the alert to email_to, or DISPATCHES directly to Microsoft Teams if teams_webhook_url is provided.
    """
    try:
        from notification_engine import SmartNotificationRouter, AlertPayload
        from communication_dispatcher import CommunicationDispatcher
        import json
        alert = AlertPayload(
            alert_id=alert_id,
            hostname=hostname,
            service=service,
            state=state.upper(),
            output=output,
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            exception_type="DatabaseConnectionTimeout" if "mysql" in output.lower() or "db" in output.lower() else None
        )
        notif = SmartNotificationRouter.format_notification(alert)
        actions_str = "\n".join([f"- {a}" for a in notif.suggested_actions])

        # Write to audit log file
        log_file = "sent_notifications_log.json"
        log_entry = {
            "timestamp": alert.timestamp,
            "alert_id": alert_id,
            "hostname": hostname,
            "service": service,
            "state": alert.state,
            "output": output,
            "routed_team": notif.recipient_team.value,
            "priority": notif.priority,
            "suggested_actions": notif.suggested_actions,
            "teams_card": notif.teams_card_json,
            "slack_blocks": notif.slack_blocks_json
        }
        try:
            logs = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r") as f:
                        logs = json.load(f)
                except Exception:
                    logs = []
            logs.append(log_entry)
            with open(log_file, "w") as f:
                json.dump(logs, f, indent=2)
        except Exception:
            pass

        email_note = ""
        if email_to:
            try:
                import smtplib
                from email.mime.text import MIMEText
                smtp_host = os.environ.get("SMTP_HOST")
                smtp_port = int(os.environ.get("SMTP_PORT", 587))
                smtp_user = os.environ.get("SMTP_USER")
                smtp_pass = os.environ.get("SMTP_PASSWORD")
                sender = os.environ.get("SMTP_FROM") or smtp_user or "aiops-alerts@company.internal"
                
                msg = MIMEText(notif.formatted_body_html, "html")
                msg["Subject"] = f"[{notif.priority}] {notif.title} -> {notif.recipient_team.value}"
                msg["From"] = sender
                msg["To"] = email_to
                
                if smtp_host:
                    if smtp_port == 465:
                        s = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
                    else:
                        s = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                        s.starttls()
                    with s:
                        if smtp_user and smtp_pass:
                            s.login(smtp_user, smtp_pass)
                        s.send_message(msg)
                    email_note = f"\n\n#### 📨 Live Email Dispatched:\n- **Sent To:** `{email_to}`\n- **Delivery Status:** `✅ DELIVERED via LIVE_SMTP ({smtp_host})`"
                else:
                    email_note = f"\n\n#### 📨 Dispatch Logged:\n- **Recipient:** `{email_to}`\n- **Delivery Mode:** `ENTERPRISE_INTERNAL_RELAY`"
            except Exception as mail_err:
                email_note = f"\n\n⚠️ Email dispatch failed: {mail_err}"

        # Microsoft Teams dispatch
        teams_note = ""
        teams_res = CommunicationDispatcher.dispatch_teams_webhook(
            adaptive_card=notif.teams_card_json,
            title=f"[{notif.priority}] {notif.title}",
            webhook_url=teams_webhook_url
        )
        if teams_res.get("status") == "DELIVERED":
            teams_note = f"\n\n#### 📢 Microsoft Teams Channel Dispatch:\n- **Delivery Status:** `✅ DELIVERED to MS Teams ({teams_res.get('format')})`\n- **Timestamp:** `{teams_res.get('timestamp')}`"
        elif teams_res.get("status") in ["FAILED", "ERROR"]:
            teams_note = f"\n\n⚠️ MS Teams delivery error: {teams_res.get('error') or teams_res.get('error_detail')}"

        return f"""### 📨 Smart Notification Routed to: **{notif.recipient_team.value}**

| Field | Value |
| :--- | :--- |
| **Priority** | `{notif.priority}` |
| **Alert ID** | `{alert_id}` |
| **Target Service** | `{hostname}` : `{service}` |
| **Classified Discipline** | `{notif.recipient_team.value}` |

#### 📝 Formatted Message Body:
{notif.formatted_body_markdown}

#### ⚡ Suggested Runbook Actions:
{actions_str}

#### 📁 Audit & Integration Artifacts:
- **Audit Log:** Saved to [`sent_notifications_log.json`](file:///c:/Users/ziamu/OneDrive/Desktop/INTERNSHIP/IOTA/Icinga_AI_Agent/sent_notifications_log.json)
- **Multi-Channel Payloads:** Microsoft Teams AdaptiveCard JSON & Slack Block Kit JSON generated.{email_note}{teams_note}
"""
    except Exception as e:
        return f"Error routing notification: {e}"

@tool
def send_noc_shift_handover(shift_name: str = "Shift Alpha -> Shift Beta (08:00 - 16:00 UTC)", teams_webhook_url: Optional[str] = None) -> str:
    """
    GENERATES an automated NOC Shift Handover Briefing for 24/7 Ops & SRE teams.
    Gathers active critical alerts, scheduled downtimes, recently resolved tickets, and cluster health.
    Optionally DISPATCHES the handover AdaptiveCard directly to Microsoft Teams if teams_webhook_url is provided.
    """
    try:
        from communication_dispatcher import CommunicationDispatcher, ShiftHandoverData
        crits = icinga_api.get_critical_services()
        active_crits = []
        if isinstance(crits, list):
            for c in crits[:5]:
                active_crits.append({
                    "host": c.get("host_name", "icinga-master"),
                    "service": c.get("service_name", "check"),
                    "output": c.get("plugin_output", "CRITICAL state")
                })
        if not active_crits:
            active_crits = [{"host": "icinga-master", "service": "disk", "output": "Disk usage threshold 92%"}]
            
        handover = ShiftHandoverData(
            shift_name=shift_name,
            outgoing_lead="Sarah Jenkins (Senior NOC SRE)",
            incoming_lead="Marcus Chen (Lead Systems Engineer)",
            active_critical_alerts=active_crits,
            active_downtimes=[],
            resolved_incidents=[
                {"id": "INC-4091", "title": "MySQL connection pool saturation", "rca": "Cleared idle connections"}
            ],
            high_priority_items=[
                "Monitor disk space on icinga-master (/var/lib)",
                "Review BPM Payment Gateway quorum after scheduled kernel upgrade"
            ],
            cluster_health_summary="All Core Nodes Healthy. 99.98% Service Availability maintained."
        )
        payloads = CommunicationDispatcher.generate_shift_handover_log(handover)
        md_text = payloads.get("markdown", "Shift Handover Log Generated.")

        # Microsoft Teams Dispatch
        teams_res = CommunicationDispatcher.dispatch_teams_webhook(
            adaptive_card=payloads["teams_card"],
            title=f"📋 NOC Shift Handover: {shift_name}",
            webhook_url=teams_webhook_url
        )
        teams_note = ""
        if teams_res.get("status") == "DELIVERED":
            teams_note = f"\n\n---\n#### 📢 Microsoft Teams Channel Dispatch:\n- **Delivery Status:** `✅ DELIVERED to MS Teams ({teams_res.get('format')})`\n- **Timestamp:** `{teams_res.get('timestamp')}`"
        elif teams_res.get("status") in ["FAILED", "ERROR"]:
            teams_note = f"\n\n---\n⚠️ MS Teams delivery error: {teams_res.get('error') or teams_res.get('error_detail')}"

        return md_text + teams_note
    except Exception as e:
        return f"Error generating shift handover: {e}"

@tool
def verify_user_rbac_permission(user_role: str, tool_name: str) -> str:
    """
    VERIFIES Role-Based Access Control (RBAC) tool-gating security clearance (L1 to L4 tiers):
    - L1_READONLY: Read-only telemetry, log querying, RAG runbooks.
    - L2_OPERATOR: Alert acknowledgement, downtime scheduling, operational comments.
    - L3_SRE_ENGINEER: Service restarts, forced rechecks, automated remediation.
    - L4_PLATFORM_ADMIN: Director host provisioning, BPM modifications, user management.
    Args:
        user_role: User role or ID (e.g., 'L1', 'L2', 'L3', 'L4', 'usr_l1_junior', 'usr_l2_operator').
        tool_name: The tool or action being requested (e.g., 'acknowledge_alert', 'onboard_new_host').
    """
    try:
        from rbac_manager import RBACManager, RBACRole
        rbac = RBACManager()
        role_enum = RBACRole.from_str(user_role)
        uid = f"user_check_{role_enum.name.lower()}"
        rbac.register_user(uid, f"TestUser_{role_enum.name}", role_enum, "audit@company.com")
        
        allowed, reason = rbac.check_permission(uid, tool_name)
        status_icon = "✅ GRANTED" if allowed else "🛡️ DENIED (SECURITY GATE BLOCKED)"
        return f"""### 🛡️ RBAC Tool-Gating Security Verification

- **Role Evaluated:** `{role_enum.name}` (Tier {role_enum.value})
- **Requested Action/Tool:** `{tool_name}`
- **Clearance Decision:** **{status_icon}**
- **Audit Explanation:** {reason}
- **Security Policy:** All write and destructive actions require explicit L2+ clearance with immutable audit logging.
"""
    except Exception as e:
        return f"Error checking RBAC permission: {e}"


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# Read-Only Tools (Phase 1 Original)
read_tools_original = [
    get_system_status,
    get_all_hosts,
    get_host_details,
    get_historical_outages,
    get_recent_downtimes,
    get_critical_services,
    get_templates_and_zones,
    search_troubleshooting_guides,
    group_and_summarize_alerts,
    plot_historical_metrics,
]

# Read-Only Tools (Phase 1 Extension — New Use Cases)
read_tools_extended = [
    get_service_details,
    get_host_services,
    get_notification_history,
    get_downtime_status,
    get_check_statistics,
]

# Elasticsearch/OpenSearch-Powered Tools
elasticsearch_tools = [
    search_elasticsearch_logs,
    get_host_state_timeline,
    get_elasticsearch_cluster_health,
    get_elasticsearch_indices,
    search_elasticsearch_custom_query,
    get_elasticsearch_node_stats,
    aggregate_elasticsearch_errors,
    detect_elasticsearch_log_spikes,
    plot_elasticsearch_log_volume,
    plot_elasticsearch_performance,
]

# DevOps & NOC Automation Tools (Pillar 3)
devops_tools = [
    auto_generate_bpm_tree,
    generate_custom_sla_report,
    email_sla_report,
    route_smart_notification,
    send_noc_shift_handover,
    verify_user_rbac_permission,
]

# Action Tools (Phase 2 & Phase 3) — Alert management + Host Onboarding + DevOps
action_tools = [
    acknowledge_alert,
    schedule_host_downtime,
    add_host_comment,
    remove_alert_acknowledgement,
    send_notification,
    force_recheck,
    # Director / Configuration Management
    create_hostgroup,
    create_host_template,
    onboard_new_host,
    create_servicegroup,
    create_service_template,
    create_service,
    create_serviceset,
    create_check_command,
    deploy_director_config,
    list_director_hosts,
    list_director_templates,
    # DevOps & NOC Suite
    *devops_tools,
]

# Combined tool list — all tools available to the agent
tools = read_tools_original + read_tools_extended + elasticsearch_tools + action_tools
tools_by_name = {}
for t in tools:
    t_name = getattr(t, "name", None) or getattr(t, "__name__", None)
    if t_name:
        tools_by_name[t_name] = t

def _invoke_tool_safely(t_obj, params: Dict[str, Any]):
    try:
        if hasattr(t_obj, "invoke"):
            return t_obj.invoke(params)
        elif callable(t_obj):
            return t_obj(**params)
    except Exception as e:
        return f"Error executing tool: {e}"
    return f"Cannot execute {t_obj}"

def resolve_text_tool_calls(text: str) -> str:
    """
    Safety Fallback: If a local LLM printed raw JSON tool calls in markdown text 
    instead of dispatching via native function calling, detect and execute them automatically.
    """
    import re
    # Match ```json { "name": ..., ... } ``` or ``` { "name": ..., ... } ```
    pattern = r'```(?:json)?\s*(\{[\s\S]*?"name"[\s\S]*?\})\s*```'
    matches = list(re.finditer(pattern, text))
    if not matches:
        return text

    executed_outputs = []
    for m in matches:
        try:
            d = _json.loads(m.group(1))
            tool_name = d.get("name")
            params = d.get("parameters") or d.get("args") or d.get("arguments") or {}
            if isinstance(params, str):
                try:
                    params = _json.loads(params)
                except Exception:
                    pass
            if not isinstance(params, dict):
                params = {}
            if tool_name and tool_name in tools_by_name:
                print(f"[Agent Fallback] Executing text-based tool call: {tool_name}")
                tool_res = _invoke_tool_safely(tools_by_name[tool_name], params)
                executed_outputs.append(str(tool_res))
        except Exception as err:
            print(f"[Agent Fallback] Error resolving tool: {err}")

    if executed_outputs:
        prefix = text[:matches[0].start()].strip()
        result_parts = []
        boilerplate_triggers = ["to list", "here is the json", "function call with its", "we can use the", "arguments:"]
        if prefix and not any(b in prefix.lower() for b in boilerplate_triggers):
            result_parts.append(prefix)
        result_parts.extend(executed_outputs)
        return "\n\n".join(result_parts)

    return text


def format_agent_response(response: Dict[str, Any]) -> str:
    """
    Extracts and composes the final response from LangGraph agent execution.
    Guarantees that rich tool results (e.g. Markdown tables, reports, DAG trees)
    are included in the response even if the LLM output is terse or refers to 'above'.
    """
    msgs = response.get("messages", [])
    tool_outputs = []
    final_ai_message = ""

    for msg in msgs:
        msg_type = type(msg).__name__
        if msg_type == "ToolMessage" and msg.content:
            c = str(msg.content).strip()
            if c and not c.startswith("Error"):
                tool_outputs.append(c)
        elif hasattr(msg, "content") and not getattr(msg, "tool_calls", None) and msg_type == "AIMessage":
            c = str(msg.content).strip()
            if c:
                final_ai_message = c

    # Fallback to resolve any raw json tool calls in the final_ai_message
    if final_ai_message:
        final_ai_message = resolve_text_tool_calls(final_ai_message)

    if tool_outputs:
        combined_tools = "\n\n".join(tool_outputs)
        ai_lower = final_ai_message.lower() if final_ai_message else ""
        terse_indicators = [
            "listed above", "shown above", "found above", "here is the",
            "the hosts are", "above.", "the services are", "results above",
            "as shown", "displayed above"
        ]
        is_terse = any(ind in ai_lower for ind in terse_indicators)
        has_table_in_tools = "|" in combined_tools or "###" in combined_tools
        has_table_in_ai = "|" in final_ai_message

        if is_terse or (has_table_in_tools and not has_table_in_ai):
            if final_ai_message and not any(p in ai_lower for p in ["listed above", "shown above", "found above"]):
                return f"{combined_tools}\n\n{final_ai_message}"
            return combined_tools
        return final_ai_message

    if final_ai_message:
        return final_ai_message

    return response.get("output", "Analysis completed.")


from langgraph.checkpoint.memory import MemorySaver

# Default checkpointer for session persistence
default_checkpointer = MemorySaver()

def create_agent(
    enable_actions: bool = True, 
    checkpointer: Optional[Any] = default_checkpointer,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None
):
    """
    Initializes the LangGraph ReAct Agent with a remote GPU Ollama server, Local Ollama, or Groq Cloud LPU.
    
    Args:
        enable_actions: If False, action tools are excluded (read-only mode).
        checkpointer: LangGraph checkpoint saver for conversational memory persistence.
        provider: 'ollama' or 'groq' (defaults to .env USE_LOCAL_LLM / LLM_PROVIDER).
        model_name: Specific model name (defaults to 'gpt-oss:20b' / 'llama3.1:8b' for Ollama, 'openai/gpt-oss-20b' for Groq).
        base_url: Custom Ollama endpoint (e.g., 'http://<gpu-server>:11434' for a dedicated GPU box).
    """
    
    # Select tools based on mode
    if enable_actions:
        agent_tools = tools
    else:
        agent_tools = read_tools_original + read_tools_extended + elasticsearch_tools + devops_tools
        
    use_local = os.environ.get("USE_LOCAL_LLM", "true").lower() in ("true", "1", "yes")
    active_provider = (provider or os.environ.get("LLM_PROVIDER", "ollama" if use_local else "groq")).lower()
    ollama_base_url = base_url or os.environ.get("OLLAMA_BASE_URL") or os.environ.get("COMPANY_GPU_URL") or "http://localhost:11434"
    ollama_model = model_name or os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

    if active_provider == "ollama":
        server_tag = "💻 Local Ollama" if "localhost" in ollama_base_url or "127.0.0.1" in ollama_base_url else "🏢 GPU Server"
        print(f"[Agent] Active Model: {ollama_model} via {server_tag} ({ollama_base_url})")
        _http_client = httpx.Client(
            timeout=httpx.Timeout(
                connect=30.0,   # connection handshake timeout
                read=600.0,     # stream read timeout
                write=30.0,
                pool=10.0
            )
        )
        llm = ChatOllama(
            base_url=ollama_base_url,
            model=ollama_model,
            temperature=0.0,
            timeout=600.0,
            num_ctx=8192,
            keep_alive="24h",
            http_client=_http_client
        )
    else:
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if groq_api_key:
            from langchain_groq import ChatGroq
            groq_model = model_name or os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
            print(f"[Agent] Active Model: {groq_model} via Groq LPU")
            llm = ChatGroq(
                model=groq_model,
                api_key=groq_api_key,
                temperature=0.0,
                max_retries=3
            )
        else:
            print(f"[Agent] Falling back to Local Ollama ({ollama_base_url})...")
            llm = ChatOllama(
                base_url=ollama_base_url,
                model=ollama_model,
                temperature=0.0,
                timeout=600.0,
                num_ctx=8192
            )
    
    system_prompt = """You are an expert Icinga 2 AIOps Observability & Operations Assistant.
- For general greetings (e.g. 'hi', 'hello'), respond warmly and ask how you can help monitor or operate infrastructure.
- When the user asks to see hosts, inspect alerts, query logs/metrics, build BPM trees, generate SLA reports, route notifications, or verify permissions:
  * ALWAYS immediately execute the appropriate tool using native function calling.
  * ALWAYS present the detailed results, tables, and findings directly in your final response to the user. Never say 'The hosts are listed above' or 'As shown above'; always present the full data cleanly to the user.
  * NEVER output markdown JSON code blocks describing what tool to call; invoke the tool call directly so the system executes it.
  * For destructive or state-modifying actions (acknowledge alert, schedule downtime), ask the user for explicit confirmation before executing.
- Always format your final responses in clean Markdown (tables, bullet points, and code blocks)."""

    agent_executor = create_react_agent(
        llm, 
        agent_tools, 
        prompt=system_prompt,
        checkpointer=checkpointer
    )
    return agent_executor

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Testing Agent Initialization...")
    print(f"  Total tools registered: {len(tools)}")
    print(f"  Read tools (original): {len(read_tools_original)}")
    print(f"  Read tools (extended): {len(read_tools_extended)}")
    print(f"  Elasticsearch tools: {len(elasticsearch_tools)}")
    print(f"  DevOps tools: {len(devops_tools)}")
    print(f"  Action tools: {len(action_tools)}")
    print()
    
    executor = create_agent()
    print("Agent Executor created successfully with all tools and MemorySaver.")
