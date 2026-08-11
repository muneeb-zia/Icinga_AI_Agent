from agent import create_agent
import traceback

print("Initializing agent...")
executor = create_agent(enable_actions=True)

print("Invoking agent...")
try:
    response = executor.invoke({
        "input": "Create a check command called 'check_custom_ping' using the 'ping' command.",
        "chat_history": ""
    })
    print("\n--- RESPONSE ---")
    print(response.get("output", "No output returned"))
except Exception as e:
    print("Error during invoke:")
    traceback.print_exc()
