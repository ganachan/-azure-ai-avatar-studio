"""
Multi-Agent Customer Support System with Azure AI Search RAG Integration
Stores cases in memory and retrieves relevant knowledge from Azure AI Search

Required Environment Variables:
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_API_KEY  
- AZURE_OPENAI_DEPLOYMENT_NAME
- AZURE_SEARCH_ENDPOINT
- AZURE_SEARCH_KEY
- AZURE_SEARCH_INDEX

Installation:
pip install streamlit python-dotenv requests openai semantic-kernel azure-search-documents
"""

import streamlit as st
import os
import json
import asyncio
from datetime import datetime
from io import StringIO
from dotenv import load_dotenv
from openai import AzureOpenAI

# Azure Search imports
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

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
        # Azure OpenAI
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.api_version = "2024-02-01"
        
        # Azure AI Search
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        self.search_index = os.getenv("AZURE_SEARCH_INDEX", "support-knowledge")
        
    def validate(self):
        required = [
            self.azure_endpoint, self.api_key, self.deployment_name
        ]
        return all(required)
    
    def validate_search(self):
        return all([self.search_endpoint, self.search_key, self.search_index])

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

class KnowledgeService:
    """Handles knowledge retrieval from Azure AI Search"""
    def __init__(self, config):
        self.config = config
        self.search_client = None
        if config.validate_search():
            try:
                self.search_client = SearchClient(
                    endpoint=config.search_endpoint,
                    index_name=config.search_index,
                    credential=AzureKeyCredential(config.search_key)
                )
                st.success("Connected to Azure AI Search successfully!")
            except Exception as e:
                st.warning(f"Azure AI Search connection failed: {e}")
        else:
            st.warning("Azure AI Search not configured - RAG features disabled")
    
    def search_similar_cases(self, issue_description, top_k=3):
        """Search for similar cases based on issue description"""
        if not self.search_client:
            return []
        
        try:
            # First, let's try without specifying select fields to see what's available
            results = self.search_client.search(
                search_text=issue_description,
                top=top_k,
                include_total_count=True
            )
            return list(results)
        except Exception as e:
            st.error(f"Search error: {e}")
            # Try a more basic search without any field specifications
            try:
                results = self.search_client.search(
                    search_text=issue_description,
                    top=top_k
                )
                return list(results)
            except Exception as e2:
                st.error(f"Basic search also failed: {e2}")
                return []
    
    def search_by_category(self, category, top_k=2):
        """Search for knowledge by category"""
        if not self.search_client:
            return []
            
        try:
            # Try basic search first
            results = self.search_client.search(
                search_text=category,
                top=top_k
            )
            return list(results)
        except Exception as e:
            st.error(f"Category search error: {e}")
            return []

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
    """Multi-agent processing system with RAG integration"""
    def __init__(self, config, knowledge_service=None):
        self.config = config
        self.knowledge_service = knowledge_service
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
            
            "AnalysisAgent": """You are the Analysis Agent for customer support with access to historical knowledge.
                              Your role is to thoroughly analyze customer issues using both current case data and historical context:
                              1. Review case details and identify key problems
                              2. Compare with similar historical cases and their resolutions
                              3. Determine severity and impact based on past experiences
                              4. Suggest potential root causes using knowledge from previous cases
                              5. Recommend investigation approaches that have proven successful
                              Always reference relevant historical cases when making recommendations.""",
            
            "ExecutorAgent": """You are the Executor Agent for customer support.
                              Your role is to implement solutions based on analysis and historical knowledge:
                              1. Execute approved resolution plans
                              2. Follow proven procedures from similar past cases
                              3. Perform necessary technical actions
                              4. Test solutions to ensure they work
                              5. Report back on implementation status
                              Be specific about actions taken and results achieved.""",
            
            "NotificationAgent": """You are the Notification Agent for customer support.
                                  Your role is to handle communications based on case outcomes:
                                  1. Create customer-friendly summaries of resolutions
                                  2. Prepare status updates for stakeholders
                                  3. Draft follow-up communications referencing resolution steps
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
    
    def _extract_issue_from_case(self, case_data):
        """Extract the core issue description for knowledge search"""
        issue_desc = case_data.get('Issue Description', '')
        root_cause = case_data.get('Root Cause', '')
        organization = case_data.get('Organization', '')
        
        # Combine key information for better search results
        search_query = f"{issue_desc} {root_cause} {organization}".strip()
        return search_query if search_query else "general support issue"
    
    async def process_case_with_rag(self, case_data, progress_container):
        """Enhanced case processing with RAG integration"""
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
                    
                    # Enhanced prompt with RAG for Analysis Agent
                    if agent_name == "AnalysisAgent" and self.knowledge_service:
                        agent_prompt = await self._create_rag_enhanced_prompt(case_data, conversation_history, agent_name)
                    else:
                        # Standard prompt for other agents
                        agent_prompt = f"""
Previous conversation:
{conversation_history}

As the {agent_name}, provide your response to this case following your role:
{self.agents[agent_name].instructions}
                        """
                    
                    # Get agent response
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
    
    async def _create_rag_enhanced_prompt(self, case_data, conversation_history, agent_name):
        """Create RAG-enhanced prompt for Analysis Agent"""
        
        # Search for similar cases
        issue_description = self._extract_issue_from_case(case_data)
        similar_cases = self.knowledge_service.search_similar_cases(issue_description, top_k=3)
        
        # Search for relevant knowledge base articles
        kb_articles = self.knowledge_service.search_by_category("knowledge_base", top_k=2)
        
        # Build enhanced prompt
        base_prompt = f"""
Previous conversation:
{conversation_history}

As the {agent_name}, provide your response to this case following your role:
{self.agents[agent_name].instructions}
"""
        
        # Add RAG context if we have search results
        if similar_cases or kb_articles:
            rag_context = "\n\n**RELEVANT KNOWLEDGE FROM SEARCH:**\n"
            
            if similar_cases:
                rag_context += "\n**Similar Historical Cases:**\n"
                for i, case in enumerate(similar_cases, 1):
                    rag_context += f"{i}. **{case.get('title', 'N/A')}**\n"
                    rag_context += f"   Content: {case.get('content', 'N/A')}\n"
                    if case.get('resolution'):
                        rag_context += f"   Resolution: {case.get('resolution')}\n"
                    if case.get('root_cause'):
                        rag_context += f"   Root Cause: {case.get('root_cause')}\n"
                    rag_context += "\n"
            
            if kb_articles:
                rag_context += "\n**Relevant Knowledge Base Articles:**\n"
                for i, article in enumerate(kb_articles, 1):
                    rag_context += f"{i}. **{article.get('title', 'N/A')}**\n"
                    rag_context += f"   Content: {article.get('content', 'N/A')}\n\n"
            
            rag_context += """
**INSTRUCTIONS FOR USING THIS KNOWLEDGE:**
- Reference specific historical cases when they match the current issue
- Apply lessons learned from past resolutions
- Consider root causes that have been identified in similar situations
- Recommend proven solutions that have worked before
- Note any patterns or trends from the historical data
"""
            
            # Display retrieved knowledge in UI
            with st.expander("📚 Retrieved Knowledge (RAG Context)", expanded=False):
                st.markdown(rag_context)
            
            return base_prompt + rag_context
        
        else:
            st.info("No relevant historical knowledge found for this case.")
            return base_prompt
    
    async def _get_agent_response(self, agent_name, prompt):
        """Get response from a specific agent using direct API call"""
        try:
            response = self.ai_client.chat.completions.create(
                model=self.config.deployment_name,
                messages=[
                    {"role": "system", "content": self.agents[agent_name].instructions},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"API error for {agent_name}: {e}")
            return None

def main():
    st.set_page_config(
        layout="centered",
        page_title="Multi-Agent Customer Support with RAG",
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

# Optional - for RAG functionality:
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_KEY=your_search_admin_key
AZURE_SEARCH_INDEX=support-knowledge
        """)
        st.stop()
    
    # Initialize services
    storage = InMemoryStorage()
    ai_service = AIService(config)
    knowledge_service = KnowledgeService(config)
    agent_processor = MultiAgentProcessor(config, knowledge_service)
    
    # UI Header
    st.title("Multi-Agent Customer Support System with RAG")
    st.write("Enhanced with Azure AI Search knowledge retrieval for better case resolution")
    
    # RAG Status
    col1, col2 = st.columns([3, 1])
    with col1:
        if knowledge_service.search_client:
            st.success("🔍 RAG System: Connected to Azure AI Search")
        else:
            st.warning("🔍 RAG System: Not configured (operating without knowledge retrieval)")
    
    with col2:
        if st.button("🧪 Test Search"):
            if knowledge_service.search_client:
                with st.spinner("Testing search and examining index structure..."):
                    # Test search with debug info
                    test_results = knowledge_service.search_similar_cases("email issues", top_k=2)
                    st.write(f"**Search Results Found:** {len(test_results)}")
                    
                    if test_results:
                        st.write("**Available Fields in Results:**")
                        for i, result in enumerate(test_results):
                            st.write(f"**Result {i+1} fields:**")
                            for key, value in result.items():
                                st.write(f"- {key}: {str(value)[:100]}...")
                            st.write("---")
                    else:
                        st.warning("No search results found. Check your index content.")
            else:
                st.warning("Search not configured")
    
    # Show stored cases
    if st.session_state.cases:
        with st.expander(f"📁 Stored Cases ({len(st.session_state.cases)})"):
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
            
            if st.button("💾 Save Case Details", type="primary"):
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
    st.subheader("3. Multi-Agent Case Processing with RAG")
    
    if st.button("🚀 Process Latest Case with RAG-Enhanced AI Agents", type="primary"):
        latest_case = storage.fetch_latest_case()
        if latest_case:
            st.write("**Processing Case:**")
            st.json(latest_case)
            
            st.write("**RAG-Enhanced Agent Conversation:**")
            progress_container = st.empty()
            
            with st.spinner("RAG-Enhanced AI Agents processing case..."):
                asyncio.run(agent_processor.process_case_with_rag(latest_case, progress_container))
        else:
            st.warning("No cases found. Please save a case first.")
    
    # Footer
    st.markdown("---")
    st.markdown("*Powered by Azure OpenAI, Semantic Kernel, and Azure AI Search RAG*")

if __name__ == "__main__":
    main()

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