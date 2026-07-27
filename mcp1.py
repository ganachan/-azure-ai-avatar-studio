"""
MCP GitHub Server Case Summary Sender
Uses actual Model Context Protocol (MCP) to communicate with GitHub MCP server

Required Environment Variables:
- GITHUB_TOKEN
- GITHUB_OWNER  
- GITHUB_REPO

Required MCP Server:
- GitHub MCP Server running locally or accessible endpoint

Installation:
pip install streamlit python-dotenv mcp anthropic
"""

import streamlit as st
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, List, Optional
import subprocess
import sys

# MCP imports
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from anthropic import Anthropic
except ImportError:
    st.error("MCP packages not installed. Run: pip install mcp anthropic")
    st.stop()

# Load environment variables
load_dotenv(override=True)

# Load from environment variables - never hardcode secrets
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "ganachan")
GITHUB_REPO = os.getenv("GITHUB_REPO", "mcpcases")

# Set environment variables for MCP server
os.environ["GITHUB_TOKEN"] = GITHUB_TOKEN
os.environ["GITHUB_OWNER"] = GITHUB_OWNER
os.environ["GITHUB_REPO"] = GITHUB_REPO

# Page configuration
st.set_page_config(
    layout="wide",
    page_title="MCP GitHub Case Summary Sender",
    page_icon="🔗",
    initial_sidebar_state="expanded"
)

# Microsoft-style CSS
st.markdown("""
<style>
    .stApp {
        background-color: #F3F2F1;
        background-image: linear-gradient(to bottom right, #F3F2F1, #E1DFDD);
    }
    
    .main-header {
        background: linear-gradient(90deg, #0078D4 0%, #106EBE 100%);
        color: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .status-card {
        background: white;
        padding: 15px;
        border-radius: 6px;
        border-left: 4px solid #0078D4;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    .success-card {
        background: #DFF6DD;
        border-left-color: #107C10;
        color: #107C10;
    }
    
    .warning-card {
        background: #FFF4CE;
        border-left-color: #FF8C00;
        color: #8A6914;
    }
    
    .error-card {
        background: #FDE7E9;
        border-left-color: #D13438;
        color: #D13438;
    }
    
    .mcp-card {
        background: #F0F8FF;
        border: 1px solid #4A90E2;
        border-radius: 6px;
        padding: 16px;
        margin: 10px 0;
    }
    
    .stButton > button {
        background-color: #0078D4;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: 600;
        transition: background-color 0.2s;
    }
    
    .stButton > button:hover {
        background-color: #106EBE;
    }
</style>
""", unsafe_allow_html=True)

class GitHubMCPServer:
    """GitHub MCP Server handler"""
    
    def __init__(self):
        self.session = None
        self.server_process = None
        self.connected = False
        self.github_token = GITHUB_TOKEN
        self.github_owner = GITHUB_OWNER
        self.github_repo = GITHUB_REPO
        
    async def start_server(self):
        """Start the GitHub MCP server"""
        try:
            # Using GitHub's official MCP server with Docker
            server_params = StdioServerParameters(
                command="docker",
                args=[
                    "run",
                    "-i",
                    "--rm",
                    "-e",
                    "GITHUB_PERSONAL_ACCESS_TOKEN",
                    "ghcr.io/github/github-mcp-server"
                ],
                env={
                    "GITHUB_PERSONAL_ACCESS_TOKEN": self.github_token
                }
            )
            
            # Connect to MCP server
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    self.connected = True
                    
                    # Initialize session
                    await session.initialize()
                    
                    return True, "MCP GitHub server connected successfully"
                    
        except Exception as e:
            return False, f"Failed to start MCP server: {str(e)}"
    
    async def list_tools(self):
        """List available MCP tools"""
        if not self.session:
            return False, "No active MCP session"
        
        try:
            tools = await self.session.list_tools()
            return True, tools.tools if hasattr(tools, 'tools') else tools
        except Exception as e:
            return False, f"Error listing tools: {str(e)}"
    
    async def create_issue(self, title: str, body: str, labels: List[str] = None):
        """Create GitHub issue via MCP"""
        if not self.session:
            return False, "No active MCP session"
        
        try:
            # Use proper MCP tool call format
            from mcp.types import CallToolRequest
            
            result = await self.session.call_tool(
                name="create_issue",
                arguments={
                    "title": title,
                    "body": body,
                    "labels": labels or []
                }
            )
            return True, result
            
        except Exception as e:
            return False, f"Error creating issue: {str(e)}"
    
    async def create_file(self, path: str, content: str, message: str):
        """Create file via MCP"""
        if not self.session:
            return False, "No active MCP session"
        
        try:
            result = await self.session.call_tool(
                name="create_or_update_file",
                arguments={
                    "path": path,
                    "content": content,
                    "message": message
                }
            )
            
            return True, result
            
        except Exception as e:
            return False, f"Error creating file: {str(e)}"
    
    async def get_repository_info(self):
        """Get repository information via MCP"""
        if not self.session:
            return False, "No active MCP session"
        
        try:
            result = await self.session.call_tool(
                name="get_repository_info",
                arguments={}
            )
            
            return True, result
            
        except Exception as e:
            return False, f"Error getting repo info: {str(e)}"
    
    def stop_server(self):
        """Stop the MCP server"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
        self.session = None
        self.connected = False

class MCPCaseFormatter:
    """Format case summaries for MCP operations"""
    
    @staticmethod
    def format_issue_for_mcp(case_data: Dict) -> Dict:
        """Format case as MCP issue creation parameters"""
        customer_name = case_data.get("customer_name", "Unknown Customer")
        case_number = case_data.get("case_number", "N/A")
        issue_description = case_data.get("issue_description", "No description")
        resolution_summary = case_data.get("resolution_summary", "No resolution")
        organization = case_data.get("organization", "Unknown Organization")
        
        title = f"Support Case Resolved: {case_number} - {customer_name}"
        
        body = f"""# Customer Support Case Resolution

## Case Information
- **Case Number**: {case_number}
- **Customer**: {customer_name}  
- **Organization**: {organization}
- **Date Resolved**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Issue Description
{issue_description}

## Resolution Summary  
{resolution_summary}

## Next Steps
- [ ] Customer follow-up scheduled
- [ ] Documentation updated
- [ ] Case closed in system

---
*This issue was automatically created via MCP from the Microsoft AI Support System*
"""
        
        return {
            "title": title,
            "body": body,
            "labels": ["support-case", "resolved", "mcp-generated"]
        }
    
    @staticmethod
    def format_documentation_for_mcp(case_data: Dict) -> Dict:
        """Format case as MCP file creation parameters"""
        customer_name = case_data.get("customer_name", "Unknown Customer")
        case_number = case_data.get("case_number", "N/A")
        issue_description = case_data.get("issue_description", "No description")
        resolution_summary = case_data.get("resolution_summary", "No resolution")
        organization = case_data.get("organization", "Unknown Organization")
        
        content = f"""# Support Case Resolution: {case_number}

**Date**: {datetime.now().strftime('%Y-%m-%d')}  
**Customer**: {customer_name}  
**Organization**: {organization}  
**Status**: Resolved  

## Problem Description

{issue_description}

## Solution Implemented

{resolution_summary}

## Technical Details

- Multi-agent AI system analysis completed
- RAG-enhanced knowledge base consulted  
- Comprehensive testing performed
- Monitoring established

## Customer Communication

Personalized avatar video generated and delivered to customer explaining the resolution.

## Case Closure

Case successfully resolved with customer satisfaction confirmed.

---

*Generated via MCP by Microsoft AI Support System*
"""
        
        filename = f"{case_number.replace('/', '-')}-{datetime.now().strftime('%Y%m%d')}.md"
        
        return {
            "path": f"docs/support-cases/{filename}",
            "content": content,
            "message": f"Add support case documentation via MCP: {case_number}"
        }

async def init_mcp_connection():
    """Initialize MCP connection"""
    if 'mcp_server' not in st.session_state:
        st.session_state.mcp_server = GitHubMCPServer()
    
    return st.session_state.mcp_server

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <div>
            <h1 style="margin: 5px 0; color: white;">MCP GitHub Case Summary Sender</h1>
            <p style="margin: 0; color: #E1F5FE;">Send support case summaries via Model Context Protocol</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize MCP server
    try:
        mcp_server = asyncio.run(init_mcp_connection())
    except Exception as e:
        st.error(f"Failed to initialize MCP server: {e}")
        return
    
    # Sidebar
    with st.sidebar:
        st.markdown("### MCP Server Status")
        
        # Connection status
        if mcp_server.connected:
            st.markdown("""
            <div class="status-card success-card">
                🔗 MCP Server: Connected
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-card warning-card">
                🔗 MCP Server: Disconnected
            </div>
            """, unsafe_allow_html=True)
        
        # GitHub configuration
        st.markdown("### GitHub Configuration")
        if mcp_server.github_owner and mcp_server.github_repo:
            st.markdown(f"""
            <div class="mcp-card">
                <strong>Repository:</strong><br>
                {mcp_server.github_owner}/{mcp_server.github_repo}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-card error-card">
                GitHub configuration missing
            </div>
            """, unsafe_allow_html=True)
        
        # Connection controls
        st.markdown("### MCP Controls")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Connect MCP"):
                with st.spinner("Starting MCP server..."):
                    try:
                        success, message = asyncio.run(mcp_server.start_server())
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    except Exception as e:
                        st.error(f"Connection failed: {e}")
        
        with col2:
            if st.button("Disconnect"):
                mcp_server.stop_server()
                st.success("MCP server disconnected")
                st.rerun()
        
        # List available tools
        if mcp_server.connected:
            if st.button("List MCP Tools"):
                with st.spinner("Fetching MCP tools..."):
                    try:
                        success, tools = asyncio.run(mcp_server.list_tools())
                        if success:
                            st.json(tools)
                        else:
                            st.error(tools)
                    except Exception as e:
                        st.error(f"Failed to list tools: {e}")
        
        # Output options
        st.markdown("---")
        st.markdown("### Output Options")
        output_type = st.selectbox(
            "Select MCP operation:",
            ["GitHub Issue", "Documentation File", "Both"]
        )
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Case Summary for MCP")
        
        # Case input form
        with st.form("case_form"):
            case_number = st.text_input("Case Number", placeholder="e.g., TF-2024-2156")
            customer_name = st.text_input("Customer Name", placeholder="e.g., Jennifer Walsh")
            organization = st.text_input("Organization", placeholder="e.g., TechFlow Solutions")
            issue_description = st.text_area(
                "Issue Description",
                placeholder="Brief description of the customer's issue...",
                height=100
            )
            resolution_summary = st.text_area(
                "Resolution Summary", 
                placeholder="Summary of how the issue was resolved...",
                height=150
            )
            
            submitted = st.form_submit_button("Send via MCP", type="primary")
        
        # Load sample case
        if st.button("Load Sample Case"):
            st.session_state.sample_loaded = True
            st.success("Sample case data loaded - fill the form above!")
        
        # Sample data (populate form externally since form doesn't allow dynamic updates)
        if st.session_state.get('sample_loaded'):
            st.info("""
            Sample case data:
            - Case: TF-2024-2156
            - Customer: Jennifer Walsh  
            - Organization: TechFlow Solutions
            - Issue: Email communication problems
            - Resolution: Windows updates rollback and monitoring setup
            """)
        
        # Process form submission
        if submitted and mcp_server.connected:
            if not all([case_number, customer_name, issue_description]):
                st.error("Please fill in all required fields")
            else:
                case_data = {
                    "case_number": case_number,
                    "customer_name": customer_name,
                    "organization": organization,
                    "issue_description": issue_description,
                    "resolution_summary": resolution_summary
                }
                
                with st.spinner("Sending via MCP..."):
                    success_count = 0
                    
                    # Create GitHub issue via MCP
                    if output_type in ["GitHub Issue", "Both"]:
                        try:
                            issue_data = MCPCaseFormatter.format_issue_for_mcp(case_data)
                            success, result = asyncio.run(
                                mcp_server.create_issue(
                                    title=issue_data["title"],
                                    body=issue_data["body"], 
                                    labels=issue_data["labels"]
                                )
                            )
                            
                            if success:
                                st.success("GitHub issue created via MCP!")
                                st.json(result)
                                success_count += 1
                            else:
                                st.error(f"MCP issue creation failed: {result}")
                        except Exception as e:
                            st.error(f"Error creating issue: {e}")
                    
                    # Create documentation via MCP
                    if output_type in ["Documentation File", "Both"]:
                        try:
                            doc_data = MCPCaseFormatter.format_documentation_for_mcp(case_data)
                            success, result = asyncio.run(
                                mcp_server.create_file(
                                    path=doc_data["path"],
                                    content=doc_data["content"],
                                    message=doc_data["message"]
                                )
                            )
                            
                            if success:
                                st.success("Documentation created via MCP!")
                                st.json(result)
                                success_count += 1
                            else:
                                st.error(f"MCP file creation failed: {result}")
                        except Exception as e:
                            st.error(f"Error creating file: {e}")
                    
                    if success_count > 0:
                        st.balloons()
        
        elif submitted and not mcp_server.connected:
            st.error("Please connect to MCP server first")
    
    with col2:
        st.subheader("MCP Status")
        
        # MCP server information
        if mcp_server.connected:
            st.markdown("""
            <div class="mcp-card">
                <h4>🔗 MCP Connection Active</h4>
                <p>GitHub MCP server is running and ready to receive commands.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Get repository info via MCP
            if st.button("Get Repo Info via MCP"):
                with st.spinner("Fetching via MCP..."):
                    try:
                        success, info = asyncio.run(mcp_server.get_repository_info())
                        if success:
                            st.json(info)
                        else:
                            st.error(info)
                    except Exception as e:
                        st.error(f"Failed to get repo info: {e}")
        else:
            st.markdown("""
            <div class="status-card warning-card">
                <h4>⚠️ MCP Server Required</h4>
                <p>You need to install and configure a GitHub MCP server.</p>
                <br>
                <strong>Installation:</strong><br>
                <code>npm install -g @modelcontextprotocol/server-github</code>
                <br><br>
                <strong>Environment Variables:</strong><br>
                <code>GITHUB_TOKEN=your_token</code><br>
                <code>GITHUB_OWNER=username</code><br>
                <code>GITHUB_REPO=repository</code>
            </div>
            """, unsafe_allow_html=True)
        
        # MCP Protocol info
        with st.expander("About MCP"):
            st.markdown("""
            **Model Context Protocol (MCP)** enables standardized communication between AI assistants and external services.
            
            This app uses MCP to:
            - Connect to GitHub repositories
            - Create issues and files
            - Maintain protocol compliance
            - Enable tool discovery
            """)

if __name__ == "__main__":
    main()