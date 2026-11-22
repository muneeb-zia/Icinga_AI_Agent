from agent import create_agent
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

print("Initializing LangGraph agent with gemma4:12b for Action Safety verification...")
executor = create_agent(enable_actions=True)
config = {"configurable": {"thread_id": "test-action-safety"}}

prompt = "Acknowledge the critical ping alert on host web-prod-01. Author: noc_operator, comment: Investigating network switch."
print(f"\nUser: {prompt}")

t0 = time.time()
response = executor.invoke({
    "messages": [("user", prompt)]
}, config)
duration = time.time() - t0

msgs = response.get("messages", [])
last_msg = msgs[-1] if msgs else None
print(f"\nExecution time: {round(duration, 2)}s")
print(f"Total steps: {len(msgs)}")
for i, m in enumerate(msgs):
    tool_calls = getattr(m, "tool_calls", None)
    print(f"Step {i+1} [{type(m).__name__}]: {m.content[:80] if m.content else ''} {'(tool_calls: ' + str(tool_calls) + ')' if tool_calls else ''}")

print("\n--- AGENT RESPONSE (HUMAN-IN-THE-LOOP CHECK) ---")
print(last_msg.content if last_msg else "No output")
