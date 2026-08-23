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

# =============================================================================
# READ TOOLS — Phase 1 (Original)
# =============================================================================

@tool
def get_system_status() -> str:
    """Queries the Icinga API for a high-level dashboard overview (total hosts, active checks, version)."""
    return str(icinga_api.get_system_status())

@tool
def get_all_hosts(filter_state: Optional[str] = None) -> str:
    """
    Queries all hosts in Icinga.
    Optionally filter by state: 'UP', 'DOWN', or 'UNREACHABLE'.

    """
    return str(icinga_api.get_all_hosts(filter_state))

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
    return str(icinga_api.get_critical_services())

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
def plot_historical_metrics(query_json: str) -> str:
    """
    Plots the historical time-series data for a specific metric and returns a visual graph.
    Use this when the user asks to 'show me the trend', 'plot the cpu', 'visualize the past data', etc.
    It returns a markdown image string that the UI will automatically render.
    
    IMPORTANT: You MUST use the exact ReAct format below, do NOT output a python function call!
    Action: plot_historical_metrics
    Action Input: {"hostname": "icinga-master", "metric_name": "cpu"}
    """
    try:
        import json
        params = json.loads(query_json)
        hostname = params.get("hostname")
        metric_name = params.get("metric_name")
        if not hostname or not metric_name:
            return "Error: hostname and metric_name are required."
    except Exception as e:
        return f"Error parsing input JSON: {str(e)}"

    # Fetch data
    # Standard Graphite metric format: icinga2.<hostname>.cpu.usage
    target_metric = f"icinga2.{hostname}.{metric_name}.usage" 
    result = graphite_api.get_historical_data(target_metric)
    
    if "error" in result or not result.get("data"):
        return f"Could not fetch historical data for {hostname} - {metric_name}."
        
    datapoints = result['data'][0]['datapoints']
    
    # Unpack datapoints
    y_values = [pt[0] for pt in datapoints if pt[0] is not None]
    # Convert epoch to datetime for x-axis
    x_values = [datetime.fromtimestamp(pt[1]) for pt in datapoints if pt[0] is not None]
    
    if not y_values:
        return "No valid datapoints found to plot."

    # Generate Plot
    plt.figure(figsize=(10, 4))
    plt.plot(x_values, y_values, marker='o', linestyle='-', color='b')
    plt.title(f"Historical Trend: {metric_name.upper()} on {hostname}")
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
def get_service_details(query_json: str) -> str:
    """
    Retrieves the detailed status and configuration of a specific service on a specific host.
    Use this for deep-diving into a service issue — state, output, performance data, check intervals, etc.

    IMPORTANT: Pass a JSON string with 'hostname' and 'service_name' keys.
    Action Input: {"hostname": "icinga-master", "service_name": "disk /"}
    """
    try:
        params = _json.loads(query_json)
        hostname = params.get("hostname") or params.get("host")
        service_name = params.get("service_name") or params.get("service")
        if not hostname or not service_name:
            return "Error: Both 'hostname' and 'service_name' are required."
    except Exception as e:
        return f"Error parsing input JSON: {str(e)}"
    return str(icinga_api.get_service_details(hostname, service_name))

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
# READ TOOLS — Elasticsearch-Powered (Ready for opensearch.internal:9200)
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
    Note: Requires VPN access to opensearch.internal:9200. Returns a fallback message if ES is not connected.

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
# ACTION TOOLS — Phase 2 (Write Operations with HITL Safety)
# =============================================================================

@tool
def acknowledge_alert(query_json: str) -> str:
    """
    ACKNOWLEDGES a problem on a host or service in Icinga.
    This stops Icinga from sending repeated notifications for this issue.
    Use this IMMEDIATELY when the user says 'acknowledge', 'ack', 'mark as known', or 'stop alerts for'.
    DO NOT call any other read tools first — ask for confirmation and then execute.
    ⚠️ ACTION: Confirm with the user before calling.
    Args:
        hostname: The host with the problem (e.g., 'icinga-master').
        service: Optional specific service name. If not given, acknowledges the HOST problem.
        comment: Reason for acknowledgement (default: 'Acknowledged by AI Agent').

    
    Action Input: {"hostname": "name", "service": "svc", "comment": "comment"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.acknowledge_problem(p.get("hostname"), service=p.get("service"), comment=p.get("comment", "Acknowledged by AI Agent")))
    except Exception as e: return str(e)

@tool
def schedule_host_downtime(query_json: str) -> str:
    """
    SCHEDULES a maintenance downtime window for a host (and optionally a specific service).
    During downtime, Icinga suppresses all notifications for the host/service.
    ⚠️ ACTION: This MODIFIES the monitoring system. Always describe the downtime window and confirm with the user first.
    Args:
        hostname: The host to put into downtime (e.g., 'db-master').
        duration_hours: How long the downtime should last in hours (default 2).
        comment: Reason for the downtime.
        service: Optional specific service. If not given, the whole host goes into downtime.

    
    Action Input: {"hostname": "name", "duration_hours": 2.0, "comment": "comment", "service": "svc"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.schedule_downtime(p.get("hostname"), duration_hours=float(p.get("duration_hours", 2.0)), comment=p.get("comment", "Downtime scheduled by AI Agent"), service=p.get("service")))
    except Exception as e: return str(e)

@tool
def add_host_comment(query_json: str) -> str:
    """
    ADDS a comment/note to a host or service in Icinga Web 2.
    Comments are visible to all operators in the Icinga dashboard. Useful for logging AI observations or investigation notes.
    ⚠️ ACTION: This MODIFIES the monitoring system. Confirm with the user before adding comments.
    Args:
        hostname: The host to comment on.
        comment: The note to add.
        service: Optional specific service to comment on.

    
    Action Input: {"hostname": "name", "comment": "note", "service": "svc"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.add_comment(p.get("hostname"), comment=p.get("comment"), service=p.get("service")))
    except Exception as e: return str(e)

@tool
def remove_alert_acknowledgement(query_json: str) -> str:
    """
    REMOVES an existing acknowledgement from a host or service.
    This re-enables notifications for the problem. Use when an ack was premature or the issue was misidentified.
    ⚠️ ACTION: This MODIFIES the monitoring system. Confirm with the user first.
    Args:
        hostname: The host to remove acknowledgement from.
        service: Optional specific service.

    
    Action Input: {"hostname": "name", "service": "svc"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.remove_acknowledgement(p.get("hostname"), service=p.get("service")))
    except Exception as e: return str(e)

@tool
def send_notification(query_json: str) -> str:
    """
    FORCE-SENDS a custom notification for a host or service.
    Use this to explicitly alert the on-call team about something the AI has discovered,
    even if Icinga wouldn't normally notify at this time.
    ⚠️ ACTION: This sends real notifications to on-call staff. Always confirm with the user first.
    Args:
        hostname: The host to notify about.
        comment: The notification message.
        service: Optional specific service.

    
    Action Input: {"hostname": "name", "comment": "note", "service": "svc"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.send_custom_notification(p.get("hostname"), comment=p.get("comment", "Custom notification from AI Agent"), service=p.get("service")))
    except Exception as e: return str(e)

@tool
def force_recheck(query_json: str) -> str:
    """
    FORCES an immediate re-check of a host or service.
    Use this after the user has made changes (restarted a service, cleared disk space, etc.)
    to verify the fix without waiting for the next scheduled check interval.
    ⚠️ ACTION: This triggers an immediate check execution. Confirm with the user first.
    Args:
        hostname: The host to re-check.
        service: Optional specific service to re-check.

    
    Action Input: {"hostname": "name", "service": "svc"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.reschedule_check(p.get("hostname"), service=p.get("service")))
    except Exception as e: return str(e)


# =============================================================================
# ACTION TOOLS — Director (Configuration Management)
# =============================================================================

@tool
def create_hostgroup(query_json: str) -> str:
    """CREATES a new host group in Icinga Director.
    Action Input: {"object_name": "name", "display_name": "disp"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.create_hostgroup(p.get("object_name"), p.get("display_name")))
    except Exception as e: return str(e)

@tool
def create_host_template(query_json: str) -> str:
    """CREATES a new host template.
    Action Input: {"object_name": "name", "check_command": "hostalive"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.create_host_template(p.get("object_name"), p.get("check_command", "hostalive")))
    except Exception as e: return str(e)

@tool
def onboard_new_host(query_json: str) -> str:
    """ONBOARDS a new host into Icinga Director. 'imports' must contain template names.
    Action Input: {"object_name": "name", "address": "ip", "imports": ["tpl"], "display_name": "disp", "groups": ["grp"]}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.create_host(p.get("object_name"), p.get("address"), p.get("imports", []), p.get("display_name"), p.get("groups")))
    except Exception as e: return str(e)

@tool
def create_servicegroup(query_json: str) -> str:
    """CREATES a new service group.
    Action Input: {"object_name": "name", "display_name": "disp"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.create_servicegroup(p.get("object_name"), p.get("display_name")))
    except Exception as e: return str(e)

@tool
def create_service_template(query_json: str) -> str:
    """CREATES a new service template.
    Action Input: {"object_name": "name", "check_command": "cmd"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.create_service_template(p.get("object_name"), p.get("check_command")))
    except Exception as e: return str(e)

@tool
def create_service(query_json: str) -> str:
    """CREATES a new service and attaches it to a host. 'imports' must contain template names.
    Action Input: {"object_name": "name", "host": "hostname", "imports": ["tpl"]}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.create_service(p.get("object_name"), p.get("host"), p.get("imports", [])))
    except Exception as e: return str(e)

@tool
def create_serviceset(query_json: str) -> str:
    """CREATES a new service set linked to a specific host. Director requires a host association.
    Action Input: {"object_name": "name", "host": "hostname", "description": "desc"}
    """
    import json
    try:
        p = json.loads(query_json)
        return str(icinga_actions.create_serviceset(p.get("object_name"), p.get("host"), p.get("description")))
    except Exception as e: return str(e)

@tool
def create_check_command(query_json: str) -> str:
    """CREATES a new check command plugin definition.
    Action Input: {"object_name": "name_here", "command": "command_here"}
    """
    import json
    try:
        params = json.loads(query_json)
        object_name = params.get("object_name")
        command = params.get("command")
        return str(icinga_actions.create_check_command(object_name, command))
    except Exception as e:
        return f"Error parsing JSON input: {str(e)}"

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

# Elasticsearch-Powered Tools (ready for opensearch.internal:9200)
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

# Action Tools (Phase 2) — Alert management + Host Onboarding
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
]

# Combined tool list — all tools available to the agent
tools = read_tools_original + read_tools_extended + elasticsearch_tools + action_tools


from langgraph.checkpoint.memory import MemorySaver

# Default checkpointer for session persistence
default_checkpointer = MemorySaver()

def create_agent(enable_actions: bool = True, checkpointer: Optional[Any] = default_checkpointer):
    """
    Initializes the LangGraph ReAct Agent with Gemma/Qwen and all Icinga tools.
    
    Args:
        enable_actions: If False, action tools are excluded (read-only mode).
        checkpointer: LangGraph checkpoint saver for conversational memory persistence.
    """
    
    # Select tools based on mode
    if enable_actions:
        agent_tools = tools
    else:
        agent_tools = read_tools_original + read_tools_extended + elasticsearch_tools
        
    _http_client = httpx.Client(
        timeout=httpx.Timeout(
            connect=30.0,   # connection handshake timeout
            read=600.0,     # stream read timeout
            write=30.0,
            pool=10.0
        )
    )
    llm = ChatOllama(
        base_url="http://gpu-server.internal:11434",
        model="gemma4:e4b",
        temperature=0.0,
        timeout=600.0,
        num_ctx=8192,
        http_client=_http_client
    )
    
    system_prompt = """You are an expert Icinga 2 AIOps Observability & Operations Assistant.
You have access to live infrastructure monitoring tools:
1. READ TOOLS: Query live Icinga 2 hosts, services, templates, downtime status, check latency.
2. HISTORICAL DATA: Query MySQL IDO database for historical outages and Graphite for time-series metrics.
3. LOG ANALYSIS: Search OpenSearch/Elasticsearch live logs, cluster health, and error aggregations.
4. RAG KNOWLEDGE BASE: Use `search_troubleshooting_guides` to perform Root Cause Analysis (RCA) and retrieve step-by-step remediation runbooks whenever a problem or error is detected.
5. ACTION CAPABILITIES (⚠️ HUMAN-IN-THE-LOOP SAFETY):
   - You can acknowledge alerts, schedule downtimes, add comments, force rechecks, and configure Icinga Director.
   - When the user asks you to execute an action (e.g. acknowledge an alert or schedule downtime), summarize the exact action and parameters you plan to use, and ask the user for explicit confirmation before executing.
   - When the user confirms ("yes", "proceed", "go ahead"), immediately execute the action tool.

FORMATTING RULES:
- Always format your responses in clean Markdown (use bullet points, bold text, and code blocks for commands).
- Keep explanations structured, professional, and actionable."""

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
    print(f"  Action tools: {len(action_tools)}")
    print()
    
    executor = create_agent()
    print("Agent Executor created successfully with all tools and MemorySaver.")
