"""
Model Context Protocol (MCP) Server for Icinga AIOps Agent.

Standardizes all Icinga 2 Core, Director, OpenSearch, MySQL IDO, Graphite,
and Hybrid RAG tools into the open Model Context Protocol specification.

Supports:
1. Tool Discovery (`tools/list`)
2. Tool Execution (`tools/call`)
3. Resource Discovery (`resources/list`)
4. Resource Reading (`resources/read`)
"""

import sys
import os
import json
from typing import Dict, Any, List

# Ensure parent path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import icinga_api
import icinga_actions
import elasticsearch_api
import database_api
import graphite_api
import knowledge_base
from agent import tools


# =============================================================================
# MCP TOOL REGISTRY DEFINITIONS
# =============================================================================

def get_mcp_tool_definitions() -> List[Dict[str, Any]]:
    """Returns all agent tools in standard MCP JSON Schema format."""
    mcp_tools = []
    
    for t in tools:
        schema = {
            "name": t.name,
            "description": t.description or "No description provided.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        
        # If args_schema exists from langchain tool
        if hasattr(t, "args_schema") and t.args_schema:
            try:
                if hasattr(t.args_schema, "model_json_schema"):
                    schema["inputSchema"] = t.args_schema.model_json_schema()
                elif hasattr(t.args_schema, "schema"):
                    schema["inputSchema"] = t.args_schema.schema()
            except Exception:
                pass
                
        mcp_tools.append(schema)
        
    return mcp_tools


def execute_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches an MCP tool call to the corresponding tool handler."""
    # Find matching tool
    target_tool = None
    for t in tools:
        if t.name == tool_name:
            target_tool = t
            break
            
    if not target_tool:
        return {
            "error": f"Tool '{tool_name}' not found in Icinga AIOps MCP registry.",
            "available_tools": [t.name for t in tools]
        }
        
    try:
        # Call tool with arguments
        if not arguments:
            result = target_tool.invoke({})
        else:
            # If tool accepts single string argument
            if len(arguments) == 1 and ("query" in arguments or "query_json" in arguments or "hostname" in arguments):
                val = list(arguments.values())[0]
                result = target_tool.invoke(val)
            else:
                result = target_tool.invoke(arguments)
                
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(result)
                }
            ],
            "isError": False
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error executing tool '{tool_name}': {str(e)}"
                }
            ],
            "isError": True
        }


# =============================================================================
# MCP RESOURCES (Icinga Live Telemetry & Documentation)
# =============================================================================

def get_mcp_resources() -> List[Dict[str, Any]]:
    """Returns available MCP resources for continuous context ingestion."""
    return [
        {
            "uri": "icinga://system/status",
            "name": "Icinga 2 System Health",
            "description": "High-level overview of total hosts, services, and check latency.",
            "mimeType": "application/json"
        },
        {
            "uri": "icinga://alerts/critical",
            "name": "Live Critical Alerts",
            "description": "Active services currently in CRITICAL or WARNING states.",
            "mimeType": "application/json"
        },
        {
            "uri": "icinga://runbooks/all",
            "name": "AIOps Troubleshooting Runbooks",
            "description": "Operational RCA guides and remediation procedures.",
            "mimeType": "text/markdown"
        }
    ]


def read_mcp_resource(uri: str) -> Dict[str, Any]:
    """Reads a specific MCP resource URI."""
    if uri == "icinga://system/status":
        data = icinga_api.get_system_status()
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(data, indent=2)}
    elif uri == "icinga://alerts/critical":
        data = icinga_api.get_critical_services()
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(data, indent=2)}
    elif uri == "icinga://runbooks/all":
        docs = knowledge_base.load_runbook_sections()
        text = "\n\n".join([f"# {d['title']}\n{d['content']}" for d in docs])
        return {"uri": uri, "mimeType": "text/markdown", "text": text}
    else:
        return {"error": f"Resource URI '{uri}' not found."}


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("==================================================")
    print("  ICINGA AIOPS AGENT - MCP SERVER INITIALIZATION")
    print("==================================================")
    tool_defs = get_mcp_tool_definitions()
    resources = get_mcp_resources()
    print(f"Total MCP Tools Registered: {len(tool_defs)}")
    print(f"Total MCP Resources Registered: {len(resources)}")
    print("\nSample Tools:")
    for t in tool_defs[:5]:
        print(f"  • {t['name']}: {t['description'][:60]}...")
        
    print("\nTesting MCP Tool Call: 'get_system_status'")
    res = execute_mcp_tool("get_system_status", {})
    print("Result:", res)
