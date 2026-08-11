from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from typing import Optional

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
    return str(icinga_api.get_host_details(hostname))

@tool
def get_historical_outages(hostname: str) -> str:
    """
    Queries the database for historical outages or crashes for a specific host.
    Use this to answer questions like 'has this host gone down recently?' or 'what is the history of this host?'
    """
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
    Searches the internal company troubleshooting documentation for solutions.
    Use this tool when you find a CRITICAL service or DOWN host and need to provide Root Cause Analysis (RCA) or fixing steps.
    """
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
def get_service_details(hostname: str, service_name: str) -> str:
    """
    Retrieves the detailed status and configuration of a specific service on a specific host.
    Use this for deep-diving into a service issue — state, output, performance data, check intervals, etc.

    """
    return str(icinga_api.get_service_details(hostname, service_name))

@tool
def get_host_services(hostname: str) -> str:
    """
    Lists ALL services being monitored on a specific host with their current states.
    Use this to get a complete inventory of what's being monitored on a host.

    """
    return str(icinga_api.get_host_services(hostname))

@tool
def get_notification_history(hostname: Optional[str] = None) -> str:
    """
    Retrieves recent notification configurations and history — who gets notified, via what command, etc.
    Optionally filter by hostname. Use this to answer 'who was notified?' or 'what alerts were sent?'.

    """
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
    Searches Elasticsearch for log entries matching a keyword across all Icinga indices.
    Use this for deep investigation — searching for specific error messages, patterns, or events
    in the historical log data stored in Elasticsearch.
    Note: Requires VPN access to opensearch.internal:9200. Returns a fallback message if ES is not connected.

    """
    return str(elasticsearch_api.search_logs_by_keyword(keyword, time_range))

@tool
def get_host_state_timeline(hostname: str, time_range: str = "30d") -> str:
    """
    Retrieves the UP/DOWN state change timeline for a host from Elasticsearch.
    Shows every state transition over the given period — useful for identifying recurring outage patterns.
    Note: Requires VPN access to opensearch.internal:9200. Returns a fallback message if ES is not connected.

    """
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
    ⚠️ ACTION: This MODIFIES the monitoring system. Always describe what you plan to do and confirm with the user before calling this.
    Args:
        hostname: The host with the problem (e.g., 'web-01').
        service: Optional specific service name (e.g., 'ssh'). If not given, acknowledges the host problem.
        comment: Reason for acknowledgement.

    
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


# =============================================================================
# AGENT INITIALIZATION
# =============================================================================

def create_agent(enable_actions: bool = True):
    """
    Initializes the LangChain Agent with Qwen and all Icinga tools.
    
    Args:
        enable_actions: If False, action tools are excluded (read-only mode).
    """
    
    # Select tools based on mode
    if enable_actions:
        agent_tools = tools
    else:
        agent_tools = read_tools_original + read_tools_extended + elasticsearch_tools
        
    llm = ChatOllama(
        base_url="http://gpu-server.internal:11434",
        model="gemma4:e4b",
        temperature=0.0,
        timeout=600.0,
        num_ctx=8192
    )
    
    # Define the ReAct prompt template for robust open-source model tool calling
    template = '''You are a highly capable AI Assistant integrated with an Icinga 2 monitoring system.
Your role is to act as an Observability and Operations Agent (AIOps). You have access to LIVE API data, HISTORICAL Database/Graphite records, and ACTION capabilities.

## READ Capabilities (Safe — no confirmation needed):
- Use live API tools for system health, hosts, alerts, services.
- Use DB tools for historical outages/downtimes.
- Use Elasticsearch tools for log analysis, cluster health, index info.

## ACTION Capabilities (⚠️ REQUIRES STRICT CONFIRMATION):
You can MODIFY the monitoring system (Director API and Icinga API).
- You can create Host Groups, Host Templates, Hosts, Service Groups, Service Templates, Services, Service Sets, and Check Commands.
- After creating configuration objects via Director API, you MUST call `deploy_director_config` to activate them.

### 🛡️ STRICT SAFETY & INTERACTIVITY RULES:
1. When asked to create a configuration object (like a host, command, or template), DO NOT call any unrelated tools first.
2. You MUST STRICTLY ASK the user for required fields if they are missing. Do NOT guess strict requirements.
3. For optional fields, you MUST TELL the user the default values you plan to use.
4. You MUST ask for explicit APPROVAL from the user before executing ANY action tool.
   Example response: "I will create a check command 'check_custom_ping' using the command 'ping'. Shall I proceed?"
5. When the user says "Yes, proceed" or "Yes", you MUST execute the corresponding action tool immediately using the parameters you previously collected. Do NOT ask for permission again.
6. After executing, report the result clearly.

📋 DIRECTOR CONFIGURATION WORKFLOW:
When creating objects that depend on templates (like hosts or services), ensure the template exists or create it first.
'''

    from langchain_core.prompts import PromptTemplate
    from langchain.agents import create_react_agent

    # Standard ReAct prompt
    react_template = '''You are a highly capable AI Assistant integrated with an Icinga 2 monitoring system.
Your role is to act as an Observability and Operations Agent (AIOps).

### 🛡️ STRICT SAFETY & INTERACTIVITY RULES:
1. When asked to create a configuration object (like a host, command, or template), DO NOT call any unrelated tools first.
2. You MUST STRICTLY ASK the user for required fields if they are missing.
3. You MUST ask for explicit APPROVAL from the user before executing ANY action tool.
   If you need to ask for approval, DO NOT call a tool! Just output your question to the user in the Final Answer.
4. When the user says "Yes, proceed", you MUST execute the corresponding action tool.

You have access to the following tools:
{tools}

Use the following strict format for your responses:

Question: the input question you must answer (or the user's approval)
Thought: you should always think about what to do.
Action: the action to take, should be one of [{tool_names}]
Action Input: a valid JSON object string
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer or question to the user

Previous Conversation History:
{chat_history}

Question: {input}
{agent_scratchpad}'''

    prompt = PromptTemplate.from_template(react_template)
    
    # Create the ReAct agent
    agent = create_react_agent(llm, agent_tools, prompt)
    
    # Create the Agent Executor
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=agent_tools, 
        verbose=True, 
        handle_parsing_errors="Please use the exact format: 'Thought: ... \nAction: ... \nAction Input: ...' or output 'Final Answer: ...' to talk to the user.",
        max_iterations=10
    )
    
    return agent_executor

if __name__ == "__main__":
    print("Testing Agent Initialization...")
    print(f"  Total tools registered: {len(tools)}")
    print(f"  Read tools (original): {len(read_tools_original)}")
    print(f"  Read tools (extended): {len(read_tools_extended)}")
    print(f"  Elasticsearch tools: {len(elasticsearch_tools)}")
    print(f"  Action tools: {len(action_tools)}")
    print()
    
    executor = create_agent()
    print("✅ Agent Executor created successfully with all tools.")
    
    # Quick test
    print("\nTesting a read query...")
    response = executor.invoke({"input": "Are there any recent scheduled downtimes in the history?"})
    print("\n--- QWEN RESPONSE ---")
    print(response["output"])
