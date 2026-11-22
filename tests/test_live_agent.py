import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import dotenv
dotenv.load_dotenv()

from agent import create_agent

print("1. Creating agent with actions enabled...", flush=True)
agent = create_agent(enable_actions=True)

query = "What is the system health status of Icinga? Pull live metrics."
print(f"2. Invoking agent with query: '{query}'...", flush=True)

t0 = time.time()
config = {"configurable": {"thread_id": f"test-cli-{int(time.time())}"}}
response = agent.invoke({"messages": [("user", query)]}, config)
duration = time.time() - t0

print(f"3. Agent finished in {duration:.2f}s!", flush=True)
msgs = response.get("messages", [])
print(f"   Total message steps: {len(msgs)}", flush=True)

for m in msgs:
    mtype = type(m).__name__
    if mtype == "ToolMessage":
        print(f"   [Tool Result] {m.name}: {str(m.content)[:150]}...", flush=True)
    elif hasattr(m, "tool_calls") and m.tool_calls:
        for tc in m.tool_calls:
            print(f"   [Tool Call] {tc['name']}({tc.get('args', {})})", flush=True)

final_text = msgs[-1].content if msgs else "No response"
print("\n" + "="*80, flush=True)
print("FINAL AGENT RESPONSE:\n", flush=True)
print(final_text, flush=True)
print("="*80, flush=True)
