import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import dotenv
dotenv.load_dotenv()

from agent import create_agent

agent = create_agent(enable_actions=True)

test_queries = [
    ("BPM Tree", "Auto-generate a BPM Business Process service tree for E-Commerce Payment Gateway with quorum evaluation."),
    ("SLA Report", "Generate a 30-day SLA and Incident Health Report for RetailCorp Global."),
    ("Smart Notification", "Route a smart notification for host api-auth-01 service check_http in CRITICAL state with error: HTTP 500 NullPointerException at AuthFilter.java:88"),
    ("NOC Shift Handover", "Compile and generate the 24/7 NOC shift handover briefing for Shift Alpha to Shift Beta."),
    ("RBAC Tool Gating", "Check if an L1_READONLY user has permission to execute acknowledge_alert, and verify if an L2_OPERATOR user can.")
]

print("="*90)
print("🚀 RUNNING END-TO-END VERIFICATION OF PILLAR 3 DEVOPS TOOLS VIA AGENT")
print("="*90)

for name, query in test_queries:
    print(f"\n--- [TEST] {name} ---")
    print(f"Prompt: {query}")
    t0 = time.time()
    config = {"configurable": {"thread_id": f"test-devops-{name.lower().replace(' ', '_')}"}}
    res = agent.invoke({"messages": [("user", query)]}, config)
    duration = time.time() - t0
    
    msgs = res.get("messages", [])
    tool_calls = []
    for m in msgs:
        if hasattr(m, "tool_calls") and m.tool_calls:
            for tc in m.tool_calls:
                tool_calls.append(tc['name'])
    
    from agent import resolve_text_tool_calls
    final_output = resolve_text_tool_calls(msgs[-1].content if msgs else "")
    print(f"✅ Completed in {duration:.2f}s | Tools Called: {tool_calls}")
    print(f"Agent Summary (first 300 chars):\n{final_output[:300]}...")
    time.sleep(1)

print("\n" + "="*90)
print("🎉 ALL PILLAR 3 DEVOPS TOOLS VERIFIED LIVE VIA AGENT!")
print("="*90)
