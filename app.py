import streamlit as st
from agent import create_agent
from langchain_core.messages import HumanMessage, AIMessage

# --- UI Configuration ---
st.set_page_config(page_title="Icinga AI Agent", page_icon="⚙️", layout="wide")
st.title("Icinga AI Observability Agent")

# Initialize chat history and agent in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "agent_executor" not in st.session_state:
    with st.spinner("Initializing Agent..."):
        st.session_state.agent_executor = create_agent()

# Display chat messages from history on app rerun
for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message.content)
    elif isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(message.content)

# React to user input
if prompt := st.chat_input("Ask about Icinga status, down hosts, or critical services..."):
    
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    
    # Add user message to chat history
    st.session_state.chat_history.append(HumanMessage(content=prompt))

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        with st.spinner("Agent is thinking and querying Icinga..."):
            try:
                # Invoke the agent
                # Note: We pass chat_history if the agent prompt supports it, currently we just pass input.
                # If we want memory, we could format chat_history here, but for now we keep it simple.
                response = st.session_state.agent_executor.invoke({
                    "input": prompt,
                    "chat_history": st.session_state.chat_history[:-1] # exclude the current prompt
                })
                output_text = response["output"]
                st.markdown(output_text)
                
                # Add assistant response to chat history
                st.session_state.chat_history.append(AIMessage(content=output_text))
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                # If Ollama is not running, show a helpful message
                if "Connection" in str(e) or "Max retries exceeded" in str(e):
                    st.info("Tip: Ensure Ollama is running locally and the model `qwen2.5-coder:7b` is pulled.")
