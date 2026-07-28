# Icinga 2 AI Observability Agent 🚀

This project is a highly intelligent, locally hosted **Read-Only Observability Agent** for Icinga 2. It translates natural language questions into executable API queries, correlates critical alerts, and uses a Retrieval-Augmented Generation (RAG) pipeline to provide Root Cause Analysis (RCA) for down hosts.

Built with **LangChain**, **Streamlit**, and a local **Qwen2.5-Coder** LLM.

---

## 🎯 Features (Phase 1)
- **Natural Language Icinga Queries**: Ask "List all down hosts" and the agent will dynamically query the Icinga API.
- **RAG-based Troubleshooting**: Automatically reads internal Markdown documentation to provide RCA for critical services.
- **Alert Correlation**: Summarizes multiple critical alerts to prevent alert fatigue and detect wider network outages.
- **Local & Secure**: Uses `Ollama` to run the Qwen LLM entirely on your local machine. No data is sent to OpenAI or cloud providers.

---

## ⚙️ Prerequisites

1. **Docker**: Used to run the local Icinga 2 instance.
2. **Ollama**: Must be installed and running on your host machine with the Qwen model.
3. **Python 3.10+**

### Setting up the LLM
Make sure Ollama is installed, then download the Qwen model:
```bash
ollama run qwen2.5-coder:7b
```

---

## 🚀 Setup Instructions for Testing

### 1. Start Icinga 2
A `docker-compose.yaml` is provided to spin up a local Icinga 2 lab environment.
```bash
docker compose up -d
```
*(Wait 1-2 minutes for the Icinga daemon to fully initialize).*

### 2. Install Python Dependencies
It is recommended to use a virtual environment, but you can install directly:
```bash
python -m pip install -r requirements.txt
```

### 3. Launch the AI Agent Interface
Start the Streamlit application:
```bash
python -m streamlit run app.py
```
This will open a web browser pointing to `http://localhost:8501`.

---

## 🧠 How it Works Under the Hood

The agent uses the **ReAct (Reasoning and Acting)** framework via LangChain. 
1. When you ask a question, the LLM determines which of its available Python **Tools** to use (e.g., `get_host_details()`).
2. LangChain intercepts this intent, executes the API call to Icinga, and returns the live JSON data back to the LLM.
3. The LLM synthesizes the JSON data into a clean, human-readable response.

For a deep dive into the architecture, tools, and execution workflow, please read the included `Phase1_Documentation.md` file!
