# Icinga 2 AI Agent - Phase 1 Documentation

## 1. Overview
The goal of Phase 1 was to build a **Read-Only Observability AI Agent** that connects to a local Icinga 2 instance. The agent uses a Local Large Language Model (Qwen2.5-Coder:7b) via Ollama to interpret user questions in natural language, automatically fetch live data from Icinga 2, and provide clear, contextual responses. 

As a **2-Step Extra** to make this a "very smart" product, we integrated:
1. **RAG-based Root Cause Analysis (RCA)**: The agent searches internal troubleshooting documentation when it detects a DOWN host or critical service.
2. **Alert Correlation**: The agent can group and summarize multiple alerts to prevent alert fatigue.

---

## 2. Agent Capabilities & Defined Tools (Functions)
The agent is not just a standard chatbot; it is integrated directly into the Icinga environment via specialized Python functions called **Tools**. The LLM reads the description of these functions and decides which one to call based on the user's prompt. 

These are the exact functions we defined in `agent.py` and `icinga_api.py` that give the agent its capabilities:

1. **`get_system_status()`**
   * **Capability:** Provides a high-level dashboard overview.
   * **Implementation:** Performs a `GET` request to the Icinga `/v1/status` API to fetch connected endpoints, active checks, and versions.
2. **`get_all_hosts(filter_state)`**
   * **Capability:** Lists all hosts in the system.
   * **Implementation:** Queries `/v1/objects/hosts`. It accepts an optional `filter_state` argument so the agent can smartly filter for only `UP` or `DOWN` hosts on the backend without downloading unnecessary data.
3. **`get_host_details(hostname)`**
   * **Capability:** Deep dives into a specific host.
   * **Implementation:** Queries `/v1/objects/hosts/{hostname}` to fetch assigned templates, custom variables, and performance metrics for a specific machine.
4. **`get_critical_services()`**
   * **Capability:** Identifies immediate problems and broken services.
   * **Implementation:** Queries `/v1/objects/services` filtering specifically for services currently in a CRITICAL state.
5. **`get_templates_and_zones()`**
   * **Capability:** Understands Icinga architectural configurations.
   * **Implementation:** Queries `/v1/objects/hosttemplates` and `/v1/objects/zones`.
6. **`search_troubleshooting_guides(query)`**
   * **Capability:** Root Cause Analysis (RCA) and resolution.
   * **Implementation:** Uses a RAG (Retrieval-Augmented Generation) pipeline. It converts the user's query into a mathematical vector using a HuggingFace embedding model (`all-MiniLM-L6-v2`), searches a local ChromaDB database for the closest match in our mock documentation, and returns the precise troubleshooting steps.
7. **`group_and_summarize_alerts()`**
   * **Capability:** Alert correlation to prevent alert fatigue.
   * **Implementation:** A custom Python script that analyzes the output of `get_critical_services()`, groups them by host, and provides a human-readable summary (e.g., detecting if multiple hosts are down, which implies a network outage rather than an isolated issue).

---

## 3. The Execution Workflow (Step-by-Step)
When a user types a prompt into the Streamlit UI (e.g., *"Why is host webserver-01 down?"*), the agent goes through the following **ReAct (Reasoning and Acting)** workflow:

1. **Prompt Ingestion:** The user's query is passed to `agent.py` along with a list of the 7 Tools defined above.
2. **Reasoning (Thought):** Qwen (the LLM) analyzes the prompt. It outputs an internal thought process: *"Thought: The user wants to know why webserver-01 is down. First, I need to verify its status using `get_host_details`. If it is down, I need to check for RCA using `search_troubleshooting_guides`."*
3. **Action & Execution:** Qwen outputs a text command to execute a specific tool (e.g., `Action: get_host_details`, `Action Input: webserver-01`). 
    *   **What is LangChain and how does this work?** LangChain is a Python framework that acts as the "orchestrator" between the LLM and your code. An LLM on its own is just a text generator—it cannot run code. However, LangChain is constantly monitoring the text streaming out of Qwen. The moment LangChain's `AgentExecutor` sees the exact keyword `Action: get_host_details`, it forcefully pauses Qwen's text generation. LangChain then maps that text string to the actual Python function `@tool def get_host_details()` defined in `agent.py`, extracts the "Action Input", and runs the python code on your local machine.
4. **Observation:** Once LangChain finishes running the Python function, it takes the raw JSON data returned from the Icinga API and injects it back into Qwen's context window as an `Observation`. Now Qwen is allowed to resume thinking, but it now has the live data it needs!
5. **Iteration (Optional):** If Qwen realizes the host is indeed down, it will loop back to Step 2. *"Thought: The host is DOWN. I should fetch the troubleshooting steps."* -> *"Action: search_troubleshooting_guides"*.
6. **Final Synthesis:** Once Qwen has all the data it needs, it outputs: *"Thought: I now know the final answer."* and generates a highly polished, natural language response summarizing the findings for the user.

---

## 4. Architecture & File Structure

The project is broken down into modular components:

*   **`app.py` (The Frontend)**
    *   A clean, professional Streamlit web interface for chat-based interactions.
    *   It maintains the chat history and streams responses from the LangChain agent.
*   **`agent.py` (The Brain & Router)**
    *   Initializes the LangChain `AgentExecutor` and connects it to the local Qwen model.
    *   Defines the **Tools** that the LLM is allowed to use.
    *   Uses the **ReAct (Reasoning and Acting)** framework to force the LLM to think step-by-step before querying APIs.
*   **`icinga_api.py` (The Read-Only Integration)**
    *   Connects directly to the Icinga 2 API running on Docker (`https://localhost:5665`).
    *   Implements strictly read-only `GET` endpoints (`/v1/status`, `/v1/objects/hosts`, `/v1/objects/services`).
*   **`knowledge_base.py` (The RAG Pipeline)**
    *   Reads the markdown files in `docs/` and converts them into vector embeddings.
    *   Stores them in a local ChromaDB vector database for fast semantic searching.
*   **`docs/sample_troubleshooting.md` (The Data)**
    *   Mock authentic troubleshooting procedures that the RAG pipeline reads.

---

## 5. Execution & Testing

### Command Line Interface (CLI)
You can watch the agent's internal thought process and API executions in the terminal by running:
```bash
python agent.py
```

### Streamlit UI
To test the product exactly as an end-user would see it, run:
```bash
python -m streamlit run app.py
```

## 6. Next Steps for Phase 2
Phase 1 is entirely read-only. For Phase 2, we will expand `icinga_api.py` to include `PUT` and `POST` methods, and add new `@tool` functions to `agent.py` to allow the LLM to actively provision new hosts, apply templates, and acknowledge alerts.
