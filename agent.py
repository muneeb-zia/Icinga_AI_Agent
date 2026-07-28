from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from typing import Optional

# Import our custom modules
import icinga_api
import knowledge_base

# --- Define Tools for the Agent ---

@tool
def get_system_status() -> str:
    """Queries the Icinga API for a high-level dashboard overview (total hosts, active checks, version)."""
    return str(icinga_api.get_system_status())

@tool
def get_all_hosts(filter_state: Optional[str] = None) -> str:
    """
    Queries all hosts in Icinga.
    Optionally filter by state: 'UP', 'DOWN', or 'UNREACHABLE'.
    Example: get_all_hosts(filter_state='DOWN')
    """
    return str(icinga_api.get_all_hosts(filter_state))

@tool
def get_host_details(hostname: str) -> str:
    """Retrieves specific template usage, custom variables, and performance data for a single host."""
    return str(icinga_api.get_host_details(hostname))

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

# --- Agent Initialization ---

# List of all tools available to the agent
tools = [
    get_system_status,
    get_all_hosts,
    get_host_details,
    get_critical_services,
    get_templates_and_zones,
    search_troubleshooting_guides,
    group_and_summarize_alerts
]

def create_agent():
    """Initializes the LangChain Agent with Qwen and Icinga tools."""
    
    # Initialize the LLM (Ollama)
    llm = ChatOllama(
        model="qwen2.5-coder:7b",
        temperature=0.0
    )
    
    # Define the ReAct prompt template for robust open-source model tool calling
    template = '''You are a highly capable AI Assistant integrated with an Icinga 2 monitoring system.
Your role is to act as a Read-Only Observability Agent for Phase 1.
When a user asks about system health, down hosts, or critical alerts, ALWAYS use the appropriate tools to fetch live data.
If you find a critical alert or down host, you should proactively use the `search_troubleshooting_guides` tool to provide Root Cause Analysis (RCA).
Use `group_and_summarize_alerts` if the user asks for an overview of current problems or if there are too many alerts.

Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}'''

    prompt = PromptTemplate.from_template(template)
    
    # Create the ReAct agent
    from langchain.agents import create_react_agent
    agent = create_react_agent(llm, tools, prompt)
    
    # Create the Agent Executor with parsing error handling
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True, 
        handle_parsing_errors=True,
        max_iterations=5
    )
    
    return agent_executor

if __name__ == "__main__":
    print("Testing Agent Initialization...")
    executor = create_agent()
    print("Agent Executor created successfully. Testing a call...")
    response = executor.invoke({"input": "What is the system status?"})
    print("\n--- QWEN RESPONSE ---")
    print(response["output"])
