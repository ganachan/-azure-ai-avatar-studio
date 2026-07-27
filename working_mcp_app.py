
import streamlit as st
import asyncio
import httpx
import json

st.title("Microsoft MCP Explorer - Simple Version")

# Initialize session state
if 'connected' not in st.session_state:
    st.session_state.connected = False

with st.sidebar:
    st.header("Connection")
    
    server_url = st.selectbox("Server:", [
        "https://learn.microsoft.com/api/mcp",
        "Custom"
    ])
    
    if server_url == "Custom":
        server_url = st.text_input("URL:", "http://localhost:3000")
    
    if st.button("Test Connection"):
        try:
            import httpx
            import asyncio
            
            async def test():
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(server_url)
                    return response.status_code
            
            status = asyncio.run(test())
            st.success(f"Server responded: HTTP {status}")
            
        except Exception as e:
            st.error(f"Connection failed: {e}")
    
    if st.button("Connect"):
        st.session_state.connected = True
        st.success("Connected!")

# Main content
if st.session_state.connected:
    st.header("Search Documentation")
    
    query = st.text_input("Search query:", "Azure Functions")
    
    if st.button("Search"):
        st.write(f"Searching for: {query}")
        st.info("This is a demo - real MCP integration would happen here")
else:
    st.info("Please connect using the sidebar")
