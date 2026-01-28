"""
Streamlit Chat Application with Azure OpenAI

A simple chat interface that uses Azure OpenAI with managed identity authentication.
Designed to run on Azure App Service with system-assigned managed identity.
"""

import os
import streamlit as st
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Page configuration
st.set_page_config(
    page_title="Azure OpenAI Chat",
    page_icon="💬",
    layout="centered"
)

# App title
st.title("💬 Azure OpenAI Chat")
st.markdown("---")


@st.cache_resource
def get_openai_client():
    """
    Create Azure OpenAI client using managed identity.
    Uses DefaultAzureCredential which automatically uses:
    - Managed Identity when running in Azure App Service
    - Azure CLI credentials when running locally
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        st.error("AZURE_OPENAI_ENDPOINT environment variable not set")
        st.stop()
    
    # Get token provider for Azure OpenAI using managed identity
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default"
    )
    
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21"
    )
    
    return client


def get_chat_response(client: AzureOpenAI, messages: list) -> str:
    """
    Get a chat response from Azure OpenAI.
    """
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    
    response = client.chat.completions.create(
        model=deployment,
        messages=messages,
        max_tokens=2048,
        temperature=0.7,
        stream=True
    )
    
    return response


def main():
    # Initialize session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Initialize OpenAI client
    try:
        client = get_openai_client()
    except Exception as e:
        st.error(f"Failed to initialize Azure OpenAI client: {e}")
        st.info("Make sure the app is configured with proper Azure credentials.")
        return
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get and display assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # Prepare messages for API call
                api_messages = [
                    {"role": "system", "content": "You are a helpful AI assistant. Provide clear, accurate, and helpful responses."}
                ] + [
                    {"role": m["role"], "content": m["content"]} 
                    for m in st.session_state.messages
                ]
                
                # Stream the response
                response = get_chat_response(client, api_messages)
                
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
            except Exception as e:
                full_response = f"Error: {str(e)}"
                message_placeholder.error(full_response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # Sidebar with info and controls
    with st.sidebar:
        st.header("ℹ️ About")
        st.markdown("""
        This is a demo chat application powered by **Azure OpenAI**.
        
        **Features:**
        - 🔐 Secure authentication with Managed Identity
        - 💬 Streaming chat responses
        - 📝 Conversation history
        """)
        
        st.markdown("---")
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        
        st.markdown("---")
        
        # Configuration info
        st.subheader("⚙️ Configuration")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "Not configured")
        deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
        
        st.text_input("Endpoint", value=endpoint, disabled=True)
        st.text_input("Model", value=deployment, disabled=True)


if __name__ == "__main__":
    main()
