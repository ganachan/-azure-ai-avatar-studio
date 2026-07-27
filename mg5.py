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
- AZCOSMOS_CONNSTR
- AZCOSMOS_DATABASE_NAME
- AZCOSMOS_CONTAINER_NAME

Installation:
pip install streamlit python-dotenv requests openai semantic-kernel azure-search-documents pymongo
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

# Cosmos DB imports
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

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
        self.search_index = os.getenv("AZURE_SEARCH_INDEX", "case1rag")
        
        # Cosmos DB
        self.cosmos_connection_string = os.getenv("AZCOSMOS_CONNSTR")
        self.cosmos_database_name = os.getenv("AZCOSMOS_DATABASE_NAME", "customerservice")
        self.cosmos_container_name = os.getenv("AZCOSMOS_CONTAINER_NAME", "cases")
        
    def validate(self):
        required = [
            self.azure_endpoint, self.api_key, self.deployment_name
        ]
        return all(required)
    
    def validate_search(self):
        return all([self.search_endpoint, self.search_key, self.search_index])
    
    def validate_cosmos(self):
        return bool(self.cosmos_connection_string)

class CosmosDBService:
    """Handles Cosmos DB operations for case management"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self.database = None
        self.collection = None
        self.connected = False
        
        if config.validate_cosmos():
            self._connect()
        else:
            st.warning("Cosmos DB not configured - case tracking disabled")
    
    def _connect(self):
        """Initialize connection to Cosmos DB"""
        try:
            # Initialize MongoDB client
            self.client = MongoClient(self.config.cosmos_connection_string)
            
            # Test connection
            self.client.admin.command('ping')
            
            # Get database and collection
            self.database = self.client[self.config.cosmos_database_name]
            self.collection = self.database[self.config.cosmos_container_name]
            
            self.connected = True
            st.success(f"💾 Connected to Cosmos DB: {self.config.cosmos_database_name}.{self.config.cosmos_container_name}")
            
        except Exception as e:
            st.error(f"Cosmos DB connection failed: {e}")
            self.connected = False
    
    def save_case(self, case_data):
        """Save a new case to Cosmos DB"""
        if not self.connected:
            return None
        
        try:
            # Add metadata
            case_data.update({
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "status": "created",
                "processing_log": []
            })
            
            # Insert into collection
            result = self.collection.insert_one(case_data)
            case_id = str(result.inserted_id)
            
            st.info(f"Case saved to Cosmos DB with ID: {case_id}")
            return case_id
            
        except Exception as e:
            st.error(f"Failed to save case to Cosmos DB: {e}")
            return None
    
    def log_agent_action(self, case_id, agent_name, action_type, details):
        """Log detailed agent actions, especially for executor agent"""
        if not self.connected or not case_id:
            return False
        
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "agent": agent_name,
                "action_type": action_type,
                "details": details
            }
            
            # Update the case with the new log entry
            result = self.collection.update_one(
                {"_id": case_id},
                {
                    "$push": {"processing_log": log_entry},
                    "$set": {
                        "updated_at": datetime.utcnow().isoformat(),
                        "current_agent": agent_name,
                        "status": f"processing_{agent_name.lower()}"
                    }
                }
            )
            
            if result.modified_count > 0:
                st.info(f"📝 Logged {action_type} action for {agent_name}")
                return True
            else:
                st.warning(f"Case {case_id} not found for logging")
                return False
                
        except Exception as e:
            st.error(f"Failed to log agent action: {e}")
            return False
    
    def complete_case(self, case_id, resolution_summary):
        """Mark case as completed"""
        if not self.connected or not case_id:
            return False
        
        try:
            result = self.collection.update_one(
                {"_id": case_id},
                {
                    "$set": {
                        "updated_at": datetime.utcnow().isoformat(),
                        "completed_at": datetime.utcnow().isoformat(),
                        "status": "completed",
                        "resolution_summary": resolution_summary
                    }
                }
            )
            
            if result.modified_count > 0:
                st.success(f"✅ Case {case_id} marked as completed")
                return True
            else:
                st.warning(f"Case {case_id} not found")
                return False
                
        except Exception as e:
            st.error(f"Failed to complete case: {e}")
            return False
    
    def get_case_logs(self, case_id):
        """Get processing logs for a case"""
        if not self.connected or not case_id:
            return []
        
        try:
            case = self.collection.find_one({"_id": case_id}, {"processing_log": 1})
            return case.get("processing_log", []) if case else []
        except Exception as e:
            st.error(f"Failed to get case logs: {e}")
            return []

class InMemoryStorage:
    """Stores cases in memory instead of database"""
    def __init__(self, cosmos_service=None):
        if 'cases' not in st.session_state:
            st.session_state.cases = []
        self.cosmos_service = cosmos_service
        
        # Track current case ID for Cosmos DB operations
        if 'current_case_id' not in st.session_state:
            st.session_state.current_case_id = None
    
    def save_case(self, case_data):
        try:
            case_data['_id'] = f"case_{len(st.session_state.cases) + 1}"
            case_data['timestamp'] = datetime.now().isoformat()
            st.session_state.cases.append(case_data)
            
            # Also save to Cosmos DB if available
            cosmos_id = None
            if self.cosmos_service and self.cosmos_service.connected:
                cosmos_id = self.cosmos_service.save_case(case_data.copy())
                if cosmos_id:
                    st.session_state.current_case_id = cosmos_id
            
            return True
        except Exception as e:
            st.error(f"Error saving case: {e}")
            return False
    
    def fetch_latest_case(self):
        if st.session_state.cases:
            return st.session_state.cases[-1]
        return None

class KnowledgeService:
    """Handles knowledge retrieval from Azure AI Search with proper vector search"""
    def __init__(self, config):
        self.config = config
        self.search_client = None
        self.embedding_client = None
        
        if config.validate_search():
            try:
                self.search_client = SearchClient(
                    endpoint=config.search_endpoint,
                    index_name=config.search_index,
                    credential=AzureKeyCredential(config.search_key)
                )
                
                # Initialize embedding client for vector search
                self.embedding_client = AzureOpenAI(
                    api_key=config.api_key,
                    api_version=config.api_version,
                    azure_endpoint=config.azure_endpoint
                )
                
                st.success("🔍 Connected to Azure AI Search and embedding service successfully!")
            except Exception as e:
                st.warning(f"Azure AI Search connection failed: {e}")
        else:
            st.warning("Azure AI Search not configured - RAG features disabled")
    
    def get_embedding(self, text):
        """Generate embedding for vector search"""
        if not self.embedding_client:
            return None
            
        try:
            response = self.embedding_client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"  # Make sure this matches your deployment
            )
            return response.data[0].embedding
        except Exception as e:
            st.error(f"Embedding generation failed: {e}")
            return None
    
    def search_similar_cases(self, issue_description, top_k=3):
        """Search for similar cases using vector similarity"""
        if not self.search_client:
            return []
        
        try:
            # Generate embedding for the search query
            query_embedding = self.get_embedding(issue_description)
            
            if query_embedding:
                # Vector search using the embedding
                results = self.search_client.search(
                    search_text="",  # Empty text search
                    vector_queries=[{
                        "kind": "vector",
                        "vector": query_embedding,
                        "fields": "text_vector",  # Your vector field name
                        "k": top_k
                    }],
                    select=["chunk_id", "parent_id", "chunk", "title"],  # Select actual fields
                    top=top_k
                )
            else:
                # Fallback to text search if embedding fails
                results = self.search_client.search(
                    search_text=issue_description,
                    select=["chunk_id", "parent_id", "chunk", "title"],
                    top=top_k
                )
            
            search_results = list(results)
            
            # Debug: Show what we actually found
            st.write(f"**Found {len(search_results)} results**")
            for i, result in enumerate(search_results):
                st.write(f"Result {i+1}: {result.get('title', 'No title')}")
            
            return search_results
            
        except Exception as e:
            st.error(f"Search error: {e}")
            # Try basic text search as fallback
            try:
                results = self.search_client.search(
                    search_text=issue_description,
                    select=["chunk_id", "parent_id", "chunk", "title"],
                    top=top_k
                )
                return list(results)
            except Exception as e2:
                st.error(f"Fallback search also failed: {e2}")
                return []
    
    def search_by_category(self, category, top_k=2):
        """Search for knowledge by category (text search)"""
        if not self.search_client:
            return []
            
        try:
            results = self.search_client.search(
                search_text=category,
                select=["chunk_id", "parent_id", "chunk", "title"],
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
    """Multi-agent processing system with RAG integration and Cosmos DB logging"""
    def __init__(self, config, knowledge_service=None, cosmos_service=None):
        self.config = config
        self.knowledge_service = knowledge_service
        self.cosmos_service = cosmos_service
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
                              Your role is to implement solutions with detailed technical execution:
                              
                              1. **Technical Implementation**: Provide specific commands, scripts, and procedures
                              2. **Risk Assessment**: Evaluate risks and plan rollback strategies  
                              3. **Testing Protocols**: Define comprehensive testing with specific metrics
                              4. **Documentation**: Create detailed execution logs with timestamps
                              5. **Monitoring Setup**: Establish monitoring and alerting
                              6. **Validation**: Verify solutions across environments
                              
                              ALWAYS include in your response:
                              - EXECUTION_LOG: Step-by-step actions with commands
                              - VALIDATION_RESULTS: Testing outcomes with metrics
                              - ROLLBACK_PLAN: Recovery procedures if needed
                              - MONITORING_CONFIG: Setup for ongoing monitoring
                              
                              Be extremely specific about commands, configuration changes, and validation criteria.""",
            
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
    
    def _extract_executor_details(self, response):
        """Extract structured details from executor agent response for database logging"""
        details = {
            "execution_log": [],
            "validation_results": {},
            "rollback_plan": "",
            "monitoring_config": {},
            "full_response": response
        }
        
        # Parse the response for structured information
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if 'EXECUTION_LOG' in line.upper():
                current_section = 'execution_log'
            elif 'VALIDATION_RESULTS' in line.upper():
                current_section = 'validation_results'
            elif 'ROLLBACK_PLAN' in line.upper():
                current_section = 'rollback_plan'
            elif 'MONITORING_CONFIG' in line.upper():
                current_section = 'monitoring_config'
            elif line and current_section:
                if current_section == 'execution_log':
                    details['execution_log'].append(line)
                elif current_section == 'rollback_plan':
                    details['rollback_plan'] += line + " "
        
        return details
    
    async def process_case_with_rag(self, case_data, progress_container):
        """Enhanced case processing with RAG integration and Cosmos DB logging"""
        if not self.agents:
            st.error("Agents not properly initialized")
            return
        
        # Get current case ID for logging
        case_id = getattr(st.session_state, 'current_case_id', None)
        
        # Log case processing start
        if self.cosmos_service and case_id:
            self.cosmos_service.log_agent_action(
                case_id, 
                "System", 
                "processing_started", 
                {"case_data": case_data, "timestamp": datetime.utcnow().isoformat()}
            )
            
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
            ("ManagerAgent", "Manager"),
            ("AnalysisAgent", "Analysis"), 
            ("ExecutorAgent", "Executor"),
            ("NotificationAgent", "Notification")
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
                        
                        # Log to Cosmos DB with special handling for ExecutorAgent
                        if self.cosmos_service and case_id:
                            if agent_name == "ExecutorAgent":
                                # Extract detailed execution information
                                executor_details = self._extract_executor_details(response)
                                self.cosmos_service.log_agent_action(
                                    case_id, 
                                    agent_name, 
                                    "detailed_execution", 
                                    executor_details
                                )
                            else:
                                # Standard logging for other agents
                                self.cosmos_service.log_agent_action(
                                    case_id, 
                                    agent_name, 
                                    "agent_response", 
                                    {"response": response, "timestamp": datetime.utcnow().isoformat()}
                                )
                    else:
                        st.error(f"No response from {agent_name}")
                    
                    st.write("---")
                    
                except Exception as e:
                    st.error(f"Error with {agent_name}: {e}")
                    # Log the error
                    if self.cosmos_service and case_id:
                        self.cosmos_service.log_agent_action(
                            case_id, 
                            agent_name, 
                            "error", 
                            {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
                        )
        
        # Complete the case
        if self.cosmos_service and case_id:
            resolution_summary = f"Case processed through all agents successfully. Final status: Resolved"
            self.cosmos_service.complete_case(case_id, resolution_summary)
        
        st.success("Case processing completed!")
        
        # Show processing logs from Cosmos DB
        if self.cosmos_service and case_id:
            with st.expander("📊 View Processing Logs from Database"):
                logs = self.cosmos_service.get_case_logs(case_id)
                if logs:
                    for log in logs:
                        st.write(f"**{log['agent']}** - {log['action_type']} ({log['timestamp']})")
                        if log['action_type'] == 'detailed_execution' and 'execution_log' in log['details']:
                            st.code('\n'.join(log['details']['execution_log']))
                        else:
                            st.write(f"Details: {str(log['details'])[:200]}...")
                        st.write("---")
                else:
                    st.info("No logs found")
    
    async def _create_rag_enhanced_prompt(self, case_data, conversation_history, agent_name):
        """Create RAG-enhanced prompt for Analysis Agent with correct field names"""
        
        # Search for similar cases
        issue_description = self._extract_issue_from_case(case_data)
        similar_cases = self.knowledge_service.search_similar_cases(issue_description, top_k=3)
        
        # Build enhanced prompt
        base_prompt = f"""
Previous conversation:
{conversation_history}

As the {agent_name}, provide your response to this case following your role:
{self.agents[agent_name].instructions}
"""
        
        # Add RAG context if we have search results
        if similar_cases:
            rag_context = "\n\n**RELEVANT KNOWLEDGE FROM SEARCH:**\n"
            rag_context += "\n**Similar Historical Cases:**\n"
            
            for i, case in enumerate(similar_cases, 1):
                # Use correct field names from your index
                title = case.get('title', 'N/A')
                content = case.get('chunk', 'N/A')  # 'chunk' is the actual field name
                case_id = case.get('chunk_id', 'N/A')
                
                rag_context += f"{i}. **Case ID:** {case_id}\n"
                rag_context += f"   **Title:** {title}\n"
                rag_context += f"   **Content:** {content}\n\n"
            
            rag_context += """
**INSTRUCTIONS FOR USING THIS KNOWLEDGE:**
- Reference specific historical cases when they match the current issue
- Apply lessons learned from past resolutions
- Consider patterns from similar cases
- Recommend approaches that align with historical solutions
- Note any recurring themes in the retrieved cases
"""
            
            # Display retrieved knowledge in UI
            with st.expander("Retrieved Knowledge (RAG Context)", expanded=False):
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
        page_title="Multi-Agent Customer Support with RAG & Cosmos DB",
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
AZURE_SEARCH_INDEX=case1rag

# Optional - for Cosmos DB:
AZCOSMOS_CONNSTR=mongodb+srv://username:password@cluster/
AZCOSMOS_DATABASE_NAME=customerservice
AZCOSMOS_CONTAINER_NAME=cases
        """)
        st.stop()
    
    # Initialize services
    cosmos_service = CosmosDBService(config)
    storage = InMemoryStorage(cosmos_service)
    ai_service = AIService(config)
    knowledge_service = KnowledgeService(config)
    agent_processor = MultiAgentProcessor(config, knowledge_service, cosmos_service)
    
    # UI Header
    st.title("Multi-Agent Customer Support System with RAG & Cosmos DB")
    st.write("Enhanced with Azure AI Search knowledge retrieval and Cosmos DB execution logging")
    
    # Service Status
    col1, col2, col3 = st.columns(3)
    with col1:
        if knowledge_service.search_client:
            st.success("🔍 RAG: Connected")
        else:
            st.warning("🔍 RAG: Not configured")
    
    with col2:
        if cosmos_service.connected:
            st.success("💾 Cosmos DB: Connected")
        else:
            st.warning("💾 Cosmos DB: Not configured")
    
    with col3:
        if st.button("Test Search"):
            if knowledge_service.search_client:
                with st.spinner("Testing search..."):
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
                    st.success("Case saved successfully in memory and Cosmos DB!")
                    st.rerun()
    
    # Multi-agent processing section
    st.subheader("3. Multi-Agent Case Processing with RAG & Database Logging")
    
    if st.button("Process Latest Case with RAG-Enhanced AI Agents", type="primary"):
        latest_case = storage.fetch_latest_case()
        if latest_case:
            st.write("**Processing Case:**")
            st.json(latest_case)
            
            if hasattr(st.session_state, 'current_case_id') and st.session_state.current_case_id:
                st.info(f"Cosmos DB Case ID: {st.session_state.current_case_id}")
            
            st.write("**RAG-Enhanced Agent Conversation:**")
            progress_container = st.empty()
            
            with st.spinner("RAG-Enhanced AI Agents processing case with database logging..."):
                asyncio.run(agent_processor.process_case_with_rag(latest_case, progress_container))
        else:
            st.warning("No cases found. Please save a case first.")
    
    # Footer
    st.markdown("---")
    st.markdown("*Powered by Azure OpenAI, Semantic Kernel, Azure AI Search RAG, and Cosmos DB*")

if __name__ == "__main__":
    main()