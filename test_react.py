from agent import create_agent
import traceback
import time
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

print("Initializing LangGraph agent with gemma4:12b...")
executor = create_agent(enable_actions=True)

test_prompt = "What is the troubleshooting procedure when MySQL connection limit is reached?"
print(f"Invoking agent with prompt: '{test_prompt}'...")

t0 = time.time()
try:
    config = {"configurable": {"thread_id": "test-session-1"}}
    response = executor.invoke({
        "messages": [("user", test_prompt)]
    }, config)
    duration = time.time() - t0
    print(f"\n--- EXECUTION SUCCESS ({round(duration, 2)}s) ---")
    msgs = response.get("messages", [])
    print(f"Total message steps: {len(msgs)}")
    for i, m in enumerate(msgs):
        m_type = type(m).__name__
        tool_calls = getattr(m, "tool_calls", None)
        print(f"  Step {i+1} [{m_type}]: {m.content[:100] if m.content else ''} {'(tool_calls: ' + str(tool_calls) + ')' if tool_calls else ''}")
    
    last_msg = msgs[-1] if msgs else None
    print("\n--- FINAL AGENT SYNTHESIS ---")
    print(last_msg.content if last_msg else "No output")
except Exception as e:
    print("Error during invoke:")
    traceback.print_exc()

