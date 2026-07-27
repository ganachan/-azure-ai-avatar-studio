"""
Multi-Agent Customer Support System (No Database Version)
Stores cases in memory for testing without Cosmos DB

Required Environment Variables:
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_API_KEY  
- AZURE_OPENAI_DEPLOYMENT_NAME

Installation:
pip install streamlit python-dotenv requests openai semantic-kernel
"""

import streamlit as st
import os
import json
import asyncio
from datetime import datetime
from io import StringIO
from dotenv import load_dotenv
from openai import AzureOpenAI

# Semantic Kernel imports
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies import KernelFunctionSelectionStrategy, KernelFunctionTerminationStrategy
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.functions.kernel_function_from_prompt import KernelFunctionFromPrompt
from semantic_kernel import Kernel

# Load environment variables
load_dotenv(override=True)

class Config:
    """Application configuration"""
    def __init__(self):
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.api_version = "2024-02-01"
        
    def validate(self):
        required = [self.azure_endpoint, self.api_key, self.deployment_name]
        return all(required)

class InMemoryStorage:
    """Stores cases in memory instead of database"""
    def __init__(self):
        if 'cases' not in st.session_state:
            st.session_state.cases = []
    
    def save_case(self, case_data):
        try:
            case_data['_id'] = f"case_{len(st.session_state.cases) + 1}"
            case_data['timestamp'] = datetime.now().isoformat()
            st.session_state.cases.append(case_data)
            return True
        except Exception as e:
            st.error(f"Error saving case: {e}")
            return False
    
    def fetch_latest_case(self):
        if st.session_state.cases:
            return st.session_state.cases[-1]
        return None

class AIService:
    """Handles Azure OpenAI operations"""
    def __init__(self, config):
        try:
            self.client = AzureOpenAI(
                api_key=config.api_key,
                api_version=config.api_version,
                azure_endpoint=config.azure_endpoint
            )
            self.deployment_name = config.deployment_name
        except Exception as e:
            st.error(f"Azure OpenAI initialization error: {e}")
            self.client = None
    
    def extract_labels_from_transcript(self, transcript):
        if not self.client:
            return {}
            
        prompt = f"""Extract customer support information from this transcript and return ONLY valid JSON:

{{
  "Organization": "Company name",
  "Case Number": "Case/ticket number if mentioned",
  "Customer Name": "Customer's name",
  "Issue Description": "Brief description of the problem",
  "Issue Duration": "How long the issue has been occurring",
  "Root Cause": "Suspected cause if mentioned"
}}

Transcript:
{transcript}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts information and returns valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.1,
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            st.error(f"Error extracting labels: {e}")
            return {}

class MultiAgentProcessor:
    """Multi-agent processing system"""
    def __init__(self, config):
        self.config = config
        self.agents = {}
        # Store AI client reference for direct API calls
        try:
            self.ai_client = AzureOpenAI(
                api_key=config.api_key,
                api_version=config.api_version,
                azure_endpoint=config.azure_endpoint
            )
        except Exception as e:
            st.error(f"Failed to initialize AI client: {e}")
            self.ai_client = None
        self._setup_agents()
    
    def _create_kernel(self, service_id):
        kernel = Kernel()
        kernel.add_service(
            AzureChatCompletion(
                endpoint=self.config.azure_endpoint,
                service_id=service_id,
                api_key=self.config.api_key,
                deployment_name=self.config.deployment_name,
            )
        )
        return kernel
    
    def _setup_agents(self):
        agent_configs = {
            "ManagerAgent": """You are the Manager Agent for customer support cases. 
                             Your role is to coordinate the case resolution process:
                             1. Review incoming cases and assign them for analysis
                             2. Make decisions based on analysis results
                             3. Coordinate with other agents to ensure proper resolution
                             4. Approve final solutions before implementation
                             Keep responses concise and action-oriented.""",
            
            "AnalysisAgent": """You are the Analysis Agent for customer support. 
                              Your role is to thoroughly analyze customer issues:
                              1. Review case details and identify key problems
                              2. Determine severity and impact of issues
                              3. Suggest potential root causes
                              4. Recommend investigation approaches
                              Provide detailed technical analysis with clear conclusions.""",
            
            "ExecutorAgent": """You are the Executor Agent for customer support.
                              Your role is to implement solutions:
                              1. Execute approved resolution plans
                              2. Perform necessary technical actions
                              3. Test solutions to ensure they work
                              4. Report back on implementation status
                              Be specific about actions taken and results achieved.""",
            
            "NotificationAgent": """You are the Notification Agent for customer support.
                                  Your role is to handle communications:
                                  1. Create customer-friendly summaries of resolutions
                                  2. Prepare status updates for stakeholders
                                  3. Draft follow-up communications
                                  4. Ensure all parties are informed appropriately
                                  Keep communications clear, professional, and empathetic."""
        }
        
        for name, instructions in agent_configs.items():
            try:
                self.agents[name] = ChatCompletionAgent(
                    kernel=self._create_kernel(name),
                    name=name,
                    instructions=instructions,
                )
            except Exception as e:
                st.error(f"Error creating agent {name}: {e}")
        
        # Setup workflow control functions
        self.termination_function = KernelFunctionFromPrompt(
            function_name="termination",
            prompt="""Review the conversation history to determine if the case has been fully resolved.

Look for these completion indicators:
- Manager has approved the final solution
- All necessary actions have been executed
- Customer communication has been prepared
- Case resolution is complete and satisfactory

If the case is fully resolved and approved, respond with exactly: APPROVED
Otherwise respond with: CONTINUE

History:
{{$history}}"""
        )
        
        self.selection_function = KernelFunctionFromPrompt(
            function_name="selection",
            prompt="""Determine which agent should respond next based on the conversation flow:

Workflow:
1. ManagerAgent - Reviews case and coordinates initial response
2. AnalysisAgent - Analyzes the issue and provides findings
3. ManagerAgent - Reviews analysis and decides on action
4. ExecutorAgent - Implements approved solutions
5. NotificationAgent - Prepares customer communications
6. ManagerAgent - Final approval

Choose from: ManagerAgent, AnalysisAgent, ExecutorAgent, NotificationAgent

Based on the conversation history, which agent should respond next?
Respond with only the agent name.

History:
{{$history}}"""
        )
    
    async def process_case_simple(self, case_data, progress_container):
        """Simple sequential agent processing without complex strategies"""
        if not self.agents:
            st.error("Agents not properly initialized")
            return
            
        # Format case data for processing
        case_summary = f"""
Customer Support Case for Processing:

Customer: {case_data.get('Customer Name', 'Unknown')}
Organization: {case_data.get('Organization', 'N/A')}
Case Number: {case_data.get('Case Number', 'N/A')}
Issue: {case_data.get('Issue Description', 'No description')}
Duration: {case_data.get('Issue Duration', 'Unknown')}
Suspected Cause: {case_data.get('Root Cause', 'Not specified')}
Timestamp: {case_data.get('timestamp', 'N/A')}

Please provide your analysis and recommendations for this case.
        """
        
        # Sequential processing through each agent
        agent_sequence = [
            ("ManagerAgent", "👔 Manager"),
            ("AnalysisAgent", "🔍 Analysis"), 
            ("ExecutorAgent", "⚙️ Executor"),
            ("NotificationAgent", "📧 Notification")
        ]
        
        conversation_history = case_summary
        
        with progress_container.container():
            for agent_name, agent_emoji in agent_sequence:
                if agent_name not in self.agents:
                    st.error(f"Agent {agent_name} not found")
                    continue
                    
                try:
                    st.write(f"**{agent_emoji} Agent Processing...**")
                    
                    # Create a simple prompt for each agent
                    agent_prompt = f"""
Previous conversation:
{conversation_history}

As the {agent_name}, provide your response to this case following your role:
{self.agents[agent_name].instructions}
                    """
                    
                    # Direct API call to get agent response
                    response = await self._get_agent_response(agent_name, agent_prompt)
                    
                    if response:
                        st.write(response)
                        conversation_history += f"\n\n{agent_emoji} {agent_name}: {response}"
                    else:
                        st.error(f"No response from {agent_name}")
                    
                    st.write("---")
                    
                except Exception as e:
                    st.error(f"Error with {agent_name}: {e}")
        
        st.success("Case processing completed!")
    
    async def _get_agent_response(self, agent_name, prompt):
        """Get response from a specific agent using direct API call"""
        try:
            response = self.ai_client.chat.completions.create(
                model=self.config.deployment_name,
                messages=[
                    {"role": "system", "content": self.agents[agent_name].instructions},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"API error for {agent_name}: {e}")
            return None

def main():
    st.set_page_config(
        layout="centered",
        page_title="Multi-Agent Customer Support",
        page_icon="🤖"
    )
    
    # Initialize configuration
    config = Config()
    if not config.validate():
        st.error("Missing required environment variables. Please check your .env file configuration.")
        st.code("""
# Required .env file content:
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
        """)
        st.stop()
    
    # Initialize services
    storage = InMemoryStorage()
    ai_service = AIService(config)
    agent_processor = MultiAgentProcessor(config)
    
    # UI
    st.title("Multi-Agent Customer Support System")
    st.write("Process customer support cases using coordinated AI agents (In-Memory Storage)")
    
    # Show stored cases
    if st.session_state.cases:
        with st.expander(f"Stored Cases ({len(st.session_state.cases)})"):
            for i, case in enumerate(reversed(st.session_state.cases)):
                st.write(f"**Case {len(st.session_state.cases) - i}:** {case.get('Customer Name')} - {case.get('Issue Description')}")
    
    # Transcript processing section
    st.subheader("1. Input Customer Transcript")
    
    uploaded_file = st.file_uploader("Upload transcript file", type=["txt"])
    text_input = st.text_area("Or paste transcript here:", height=200)
    
    transcript = None
    if uploaded_file:
        transcript = StringIO(uploaded_file.getvalue().decode("utf-8")).read()
    elif text_input.strip():
        transcript = text_input
    
    # Process transcript
    if transcript:
        st.subheader("2. Extracted Information")
        
        with st.spinner("Extracting information with AI..."):
            labels = ai_service.extract_labels_from_transcript(transcript)
        
        if labels:
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Customer:** {labels.get('Customer Name', 'N/A')}")
                st.write(f"**Organization:** {labels.get('Organization', 'N/A')}")
                st.write(f"**Case Number:** {labels.get('Case Number', 'N/A')}")
            
            with col2:
                st.write(f"**Issue:** {labels.get('Issue Description', 'N/A')}")
                st.write(f"**Duration:** {labels.get('Issue Duration', 'N/A')}")
                st.write(f"**Root Cause:** {labels.get('Root Cause', 'N/A')}")
            
            if st.button("Save Case Details", type="primary"):
                case_data = {
                    "Case Number": labels.get("Case Number", "N/A"),
                    "Organization": labels.get("Organization", "N/A"),
                    "Customer Name": labels.get("Customer Name", "N/A"),
                    "Issue Description": labels.get("Issue Description", "N/A"),
                    "Issue Duration": labels.get("Issue Duration", "N/A"),
                    "Root Cause": labels.get("Root Cause", "N/A")
                }
                
                if storage.save_case(case_data):
                    st.success("Case saved successfully in memory!")
                    st.rerun()
    
    # Multi-agent processing section
    st.subheader("3. Multi-Agent Case Processing")
    
    if st.button("Process Latest Case with AI Agents", type="primary"):
        latest_case = storage.fetch_latest_case()
        if latest_case:
            st.write("**Processing Case:**")
            st.json(latest_case)
            
            st.write("**Agent Conversation:**")
            progress_container = st.empty()
            
            with st.spinner("AI Agents processing case..."):
                asyncio.run(agent_processor.process_case_simple(latest_case, progress_container))
        else:
            st.warning("No cases found. Please save a case first.")

if __name__ == "__main__":
    main()