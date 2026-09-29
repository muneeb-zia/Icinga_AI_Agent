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
    
    # Operator Identity Selector (Tiered RBAC)
    import os
    st.subheader("🛡️ Operator Identity (RBAC)")
    role_options = {
        "👤 admin (Tier 4: Platform Admin)": "admin",
        "👤 senior_sre (Tier 2: L2 Operator)": "senior_sre",
        "👤 junior_operator (Tier 1: L1 Read-Only)": "junior_operator"
    }
    selected_role_label = st.selectbox(
        "Active Operator Identity",
        options=list(role_options.keys()),
        index=0,
        help="Simulate interacting with the agent as different authenticated Icinga Web 2 operators."
    )
    current_operator = role_options[selected_role_label]
    os.environ["CURRENT_ICINGA_USER"] = current_operator
    st.caption(f"Active Identity: `{current_operator}`")
    
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
    
    # Active LLM Engine Selection
    import os
    st.subheader("🧠 LLM Engine Selection")
    model_options = {
        "🏢 Company GPU: GPT-OSS 20B (gpu-server.internal - 114 tok/s - Recommended)": ("ollama", "gpt-oss:20b", "http://gpu-server.internal:11434"),
        "🏢 Company GPU: Qwen 3 14B (gpu-server.internal - Reasoning)": ("ollama", "qwen3:14b", "http://gpu-server.internal:11434"),
        "🏢 Company GPU: Gemma 4 12B (gpu-server.internal)": ("ollama", "gemma4:12b", "http://gpu-server.internal:11434"),
        "🏢 Company GPU: Llama 3.1 8B (gpu-server.internal)": ("ollama", "llama3.1:8b-instruct-q4_K_M", "http://gpu-server.internal:11434"),
        "💻 Local Ollama: Llama 3.1 8B (Local Host)": ("ollama", "llama3.1:8b", "http://localhost:11434"),
        "⚡ Groq Cloud LPU (openai/gpt-oss-20b)": ("groq", "openai/gpt-oss-20b", None)
    }
    
    selected_label = st.selectbox(
        "Active LLM",
        options=list(model_options.keys()),
        index=0,
        help="Select between Company Dedicated GPU server, local private models, or cloud LPU."
    )
    selected_provider, selected_model, selected_base_url = model_options[selected_label]
    
    if "current_model" not in st.session_state or st.session_state.current_model != selected_model or st.session_state.get("current_base_url") != selected_base_url:
        st.session_state.current_model = selected_model
        st.session_state.current_provider = selected_provider
        st.session_state.current_base_url = selected_base_url
        if "agent_executor" in st.session_state:
            del st.session_state["agent_executor"]
            
    if selected_base_url and "gpu-server.internal" in selected_base_url:
        st.success(f"🏢 **Company 16GB GPU Server**\n\nModel: `{selected_model}`\n\nEndpoint: `{selected_base_url}`\n\nSpeed: **~114 tok/s** | VRAM: **12.7 GB resident**")
    elif selected_provider == "ollama":
        st.success(f"🟢 **Air-Gapped Private Inference**\n\nModel: `{selected_model}`\n\nEndpoint: `{selected_base_url or 'localhost:11434'}`\n\nRate Limits: **Unlimited**")
    else:
        st.info(f"⚡ **Groq Cloud LPU**\n\nModel: `{selected_model}`\n\nInference: ~175 tok/s")

    st.divider()

    # Tool count info
    from agent import read_tools_original, read_tools_extended, elasticsearch_tools, action_tools, devops_tools
    core_actions_count = len(action_tools) - len(devops_tools)
    total_tools = len(read_tools_original) + len(read_tools_extended) + len(elasticsearch_tools) + len(devops_tools)
    if action_mode:
        total_tools += core_actions_count
    
    st.subheader("🔧 Available Tools")
    st.metric("Total Tools Active", total_tools)
    st.caption(f"📖 Monitoring & RAG: {len(read_tools_original) + len(read_tools_extended)}")
    st.caption(f"🔍 OpenSearch Logs: {len(elasticsearch_tools)}")
    st.caption(f"🛠️ DevOps & NOC Suite: {len(devops_tools)}")
    if action_mode:
        st.caption(f"⚡ Core Actions (HITL): {core_actions_count}")
    else:
        st.caption("🔒 Core Actions: Disabled (Toggle above)")
    
    st.divider()
    if st.button("🗑️ Clear Chat History"):
        import uuid
        st.session_state.chat_history = []
        st.session_state.session_id = str(uuid.uuid4())
        if "agent_executor" in st.session_state:
            del st.session_state["agent_executor"]
        st.rerun()


# --- Main Chat Interface ---
st.title("Icinga AI Observability Agent")

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

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
        st.session_state.agent_executor = create_agent(
            enable_actions=action_mode,
            provider=st.session_state.get("current_provider", "ollama"),
            model_name=st.session_state.get("current_model", "gpt-oss:20b"),
            base_url=st.session_state.get("current_base_url", "http://gpu-server.internal:11434")
        )

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

# --- Interactive Quick-Test Scenarios ---
if not st.session_state.chat_history:
    st.markdown("### 💡 Quick-Test Scenarios (Click any scenario to test live):")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**🧠 Pillar 1: Semantic RAG & RCA:**")
        example_reads = [
            ("Fix Critical Disk Alert", "The disk service on icinga-master is critical. How do I fix it?"),
            ("Resolve MySQL Saturation", "How do I resolve high MySQL connection pool exhaustion?"),
            ("List All Critical Alerts", "Show me all critical alerts across our infrastructure"),
            ("Cluster Health Status", "Show me the system health status of Icinga"),
        ]
        for title, prompt_str in example_reads:
            if st.button(f"🔍 {title}", key=f"btn_p1_{title}", help=prompt_str, use_container_width=True):
                st.session_state.pending_prompt = prompt_str
                st.rerun()
    
    with col2:
        if action_mode:
            st.markdown("**⚡ Pillar 2: Alert Actions (HITL Gate):**")
            example_actions = [
                ("Acknowledge icinga-master", "Acknowledge the problem on icinga-master"),
                ("Schedule 2h Downtime", "Schedule 2 hours of downtime on icinga-master for OS patching"),
                ("Add Operational Comment", "Add a comment to icinga-master: Investigating issue"),
                ("Force Immediate Re-check", "Force a re-check on icinga-master"),
            ]
            for title, prompt_str in example_actions:
                if st.button(f"⚡ {title}", key=f"btn_p2_{title}", help=prompt_str, use_container_width=True):
                    st.session_state.pending_prompt = prompt_str
                    st.rerun()
        else:
            st.markdown("**🔍 Log & Metric Analytics:**")
            example_deep = [
                ("Search OpenSearch Logs", "Search OpenSearch logs for 'disk full'"),
                ("Plot Host CPU Trend", "Plot the CPU trend for icinga-master"),
                ("Host State Timeline", "Show the UP/DOWN state timeline for icinga-master"),
                ("Top Failing Hosts", "What are the top failing hosts in the last 24 hours?"),
            ]
            for title, prompt_str in example_deep:
                if st.button(f"📊 {title}", key=f"btn_p2_deep_{title}", help=prompt_str, use_container_width=True):
                    st.session_state.pending_prompt = prompt_str
                    st.rerun()

    with col3:
        st.markdown("**🛠️ Pillar 3: DevOps & NOC Suite:**")
        example_devops = [
            ("1. Auto-Generate BPM DAG Tree", "Auto-generate a BPM service tree for E-Commerce Payment Gateway with quorum evaluation"),
            ("2. SLA Report & Email Client", "Generate a 30-day SLA and Incident Health Report for RetailCorp Global and email it to client@retailcorp.com"),
            ("3. Route Smart Notification", "Route a smart notification for host api-auth-01 service check_http in CRITICAL state with error: HTTP 500 NullPointerException at AuthFilter.java:88"),
            ("4. 24/7 NOC Shift Handover", "Compile and generate the 24/7 NOC shift handover briefing for Shift Alpha to Shift Beta"),
            ("5. Verify L1 vs L2 RBAC Clearance", "Check if an L1 user can execute acknowledge_alert, and verify if an L2 user can"),
        ]
        for title, prompt_str in example_devops:
            if st.button(f"🛠️ {title}", key=f"btn_devops_{title}", help=prompt_str, use_container_width=True):
                st.session_state.pending_prompt = prompt_str
                st.rerun()

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
                config = {"configurable": {"thread_id": st.session_state.get("session_id", "streamlit-session")}}
                response = st.session_state.agent_executor.invoke({
                    "messages": [("user", prompt)]
                }, config)

                from agent import format_agent_response
                output_text = format_agent_response(response)

                st.markdown(output_text, unsafe_allow_html=True)
                
                # --- Plot Rendering ---
                import os
                if os.path.exists("latest_plot.png"):
                    st.image("latest_plot.png", use_container_width=True)
                    os.remove("latest_plot.png")

                # --- Live File Downloads for Executive SLA Reports ---
                if os.path.exists("enterprise_sla_report.pdf") or os.path.exists("enterprise_sla_report.xlsx"):
                    dl1, dl2 = st.columns(2)
                    if os.path.exists("enterprise_sla_report.pdf"):
                        with open("enterprise_sla_report.pdf", "rb") as f_pdf:
                            dl1.download_button(
                                label="📄 Download Branded SLA PDF Report",
                                data=f_pdf.read(),
                                file_name="enterprise_sla_report.pdf",
                                mime="application/pdf",
                                key="dl_btn_pdf"
                            )
                    if os.path.exists("enterprise_sla_report.xlsx"):
                        with open("enterprise_sla_report.xlsx", "rb") as f_xls:
                            dl2.download_button(
                                label="📗 Download Multi-Tab Excel Workbook (.xlsx)",
                                data=f_xls.read(),
                                file_name="enterprise_sla_report.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_btn_xls"
                            )
                
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
                if "Connection" in str(e) or "Max retries exceeded" in str(e):
                    st.info("Tip: Ensure Ollama is running locally at http://localhost:11434 with model `llama3.1:8b`.")
