import streamlit as st
from agent import create_agent
from langchain_core.messages import HumanMessage, AIMessage

# --- UI Configuration ---
st.set_page_config(page_title="Icinga AI Agent", page_icon="⚙️", layout="wide")

# --- Sidebar Configuration ---
with st.sidebar:
    st.title("⚙️ Agent Settings")
    st.divider()
    
    # Action Mode Toggle
    st.subheader("🔒 Action Mode")
    action_mode = st.toggle(
        "Enable Action Capabilities",
        value=False,
        help="When enabled, the agent can modify the monitoring system "
             "(acknowledge alerts, schedule downtimes, add comments, etc.). "
             "The agent will always ask for confirmation before executing actions."
    )
    
    if action_mode:
        st.warning(
            "⚠️ **Action Mode is ON**\n\n"
            "The agent can now execute write operations on Icinga. "
            "It will ask for your confirmation before any action.",
            icon="⚠️"
        )
    else:
        st.info(
            "🔒 **Read-Only Mode**\n\n"
            "The agent can only query and observe. "
            "No modifications will be made to the monitoring system.",
            icon="ℹ️"
        )
    
    st.divider()
    
    # Data Source Info
    st.subheader("📊 Data Sources")
    
    # Elasticsearch status
    import elasticsearch_api
    if elasticsearch_api.ES_ENABLED:
        st.success(f"✅ Elasticsearch: `{elasticsearch_api.ES_HOST}:{elasticsearch_api.ES_PORT}`")
    else:
        st.warning(
            f"⏳ Elasticsearch: `{elasticsearch_api.ES_HOST}:{elasticsearch_api.ES_PORT}`\n\n"
            "Not connected (VPN required). Using MySQL IDO fallback."
        )
    
    st.caption("🔄 MySQL IDO: Active (fallback)")
    import graphite_api
    if graphite_api.DEMO_MODE:
        st.caption("📈 Graphite: Demo Mode")
    else:
        st.caption(f"📈 Graphite: Active ({graphite_api.GRAPHITE_URL})")
    
    st.divider()
    
    # Tool count info
    from agent import read_tools_original, read_tools_extended, elasticsearch_tools, action_tools
    total_tools = len(read_tools_original) + len(read_tools_extended) + len(elasticsearch_tools)
    if action_mode:
        total_tools += len(action_tools)
    
    st.subheader("🔧 Available Tools")
    st.metric("Total Tools", total_tools)
    st.caption(f"📖 Read: {len(read_tools_original) + len(read_tools_extended)}")
    st.caption(f"🔍 Elasticsearch: {len(elasticsearch_tools)}")
    if action_mode:
        st.caption(f"⚡ Actions: {len(action_tools)}")
    
    st.divider()
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        if "agent_executor" in st.session_state:
            del st.session_state["agent_executor"]
        st.rerun()


# --- Main Chat Interface ---
st.title("Icinga AI Observability Agent")

if action_mode:
    st.caption("🟢 **Mode: Read + Action** — The agent can query AND modify the monitoring system.")
else:
    st.caption("🔵 **Mode: Read-Only** — The agent can query but cannot modify the monitoring system.")

# Initialize chat history and agent in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Re-initialize agent if action mode changed
current_mode = action_mode
if "current_action_mode" not in st.session_state or st.session_state.current_action_mode != current_mode:
    st.session_state.current_action_mode = current_mode
    if "agent_executor" in st.session_state:
        del st.session_state["agent_executor"]

if "agent_executor" not in st.session_state:
    with st.spinner("Initializing Agent..."):
        st.session_state.agent_executor = create_agent(enable_actions=action_mode)

# Display chat messages from history on app rerun
for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message.content, unsafe_allow_html=True)
    elif isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(message.content, unsafe_allow_html=True)
            
            # --- HITL Safety: Detect action confirmations ---
            # If the agent's last response looks like it's asking for confirmation,
            # render approve/reject buttons
            content_lower = message.content.lower()
            action_indicators = [
                "shall i proceed",
                "would you like me to",
                "do you want me to",
                "should i go ahead",
                "confirm this action",
                "do you approve",
                "shall i execute",
            ]
            if any(indicator in content_lower for indicator in action_indicators):
                # Only show buttons on the LAST AI message that asks for confirmation
                if message == [m for m in st.session_state.chat_history if isinstance(m, AIMessage)][-1]:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Yes, proceed", key=f"approve_{id(message)}"):
                            st.session_state.pending_prompt = "Yes, proceed."
                            st.rerun()
                    with col2:
                        if st.button("❌ No, cancel", key=f"reject_{id(message)}"):
                            st.session_state.pending_prompt = "No, do not execute the action. Cancel it."
                            st.rerun()

# --- Example prompts ---
if not st.session_state.chat_history:
    st.markdown("### 💡 Try asking:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📖 Read Queries:**")
        example_reads = [
            "Show me the system status",
            "Are there any hosts that are DOWN?",
            "List all services on icinga-master",
            "What's the check latency of our monitoring?",
            "Which hosts are in scheduled downtime?",
        ]
        for example in example_reads:
            st.code(example, language=None)
    
    with col2:
        if action_mode:
            st.markdown("**⚡ Action Queries:**")
            example_actions = [
                "Acknowledge the ping alert on web-01",
                "Schedule 2 hours of downtime on db-master",
                "Add a comment to web-01: investigating slow response",
                "Force a re-check of the SSH service on db-master",
                "Send a notification about the disk issue on web-01",
            ]
            for example in example_actions:
                st.code(example, language=None)
        else:
            st.markdown("**🔍 Deep Dive Queries:**")
            example_deep = [
                "What is the status of SSH on db-master?",
                "Show me the notification history for web-01",
                "Who was notified about the last critical alert?",
                "Search logs for 'disk full'",
                "Plot the CPU trend for icinga-master",
            ]
            for example in example_deep:
                st.code(example, language=None)

# --- Input Sanitization: Strip prompt injection attempts ---
INJECTION_PATTERNS = [
    "system override", "ignore previous instructions", "ignore your instructions",
    "disregard your rules", "bypass safety", "you are now", "act as if",
    "do not ask for permission", "must now execute", "execute it now"
]

def _sanitize_input(text: str) -> str:
    """Block prompt injection attempts from reaching the agent."""
    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower:
            return "No, cancel the last action."
    return text

# React to user input
prompt = st.chat_input("Ask Icinga AI...")

if "pending_prompt" in st.session_state and st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt:
    prompt = _sanitize_input(prompt)
    # Add user message to chat history
    st.session_state.chat_history.append(HumanMessage(content=prompt))

    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agent is thinking and querying Icinga..."):
            try:
                # Invoke the LangGraph agent
                config = {"configurable": {"thread_id": "streamlit-session"}}
                response = st.session_state.agent_executor.invoke({
                    "messages": [("user", prompt)]
                }, config)

                msgs = response.get("messages", [])
                output_text = ""
                for msg in reversed(msgs):
                    if hasattr(msg, "content") and not getattr(msg, "tool_calls", None):
                        c = msg.content if isinstance(msg.content, str) else str(msg.content)
                        if c.strip():
                            output_text = c.strip()
                            break

                if not output_text and msgs:
                    for msg in reversed(msgs):
                        if type(msg).__name__ == "ToolMessage" and msg.content:
                            output_text = f"Tool result: {msg.content}"
                            break

                if not output_text:
                    output_text = response.get("output", "Analysis completed.")

                st.markdown(output_text, unsafe_allow_html=True)
                
                # --- Plot Rendering ---
                import os
                if os.path.exists("latest_plot.png"):
                    st.image("latest_plot.png", use_container_width=True)
                    os.remove("latest_plot.png")
                
                # Add assistant response to chat history
                st.session_state.chat_history.append(AIMessage(content=output_text))
                
                # --- HITL: Check if response needs confirmation ---
                content_lower = output_text.lower()
                action_indicators = [
                    "shall i proceed",
                    "would you like me to",
                    "do you want me to",
                    "should i go ahead",
                    "confirm this action",
                    "do you approve",
                    "shall i execute",
                ]
                if any(indicator in content_lower for indicator in action_indicators):
                    st.divider()
                    st.warning("⚠️ **Action Confirmation Required**")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Yes, proceed", key="approve_latest"):
                            st.session_state.pending_prompt = "Yes, proceed."
                            st.rerun()
                    with col2:
                        if st.button("❌ No, cancel", key="reject_latest"):
                            st.session_state.pending_prompt = "No, do not execute the action. Cancel it."
                            st.rerun()
                            
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                # If Ollama is not running, show a helpful message
                if "Connection" in str(e) or "Max retries exceeded" in str(e):
                    st.info("Tip: Ensure Ollama is running locally and the model `qwen2.5-coder:7b` is pulled.")
