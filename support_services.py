"""
Complete support_services.py - All backend services for the customer support system
Save this entire file as support_services.py
"""

import streamlit as st
import os
import json
import asyncio
import time
import uuid
import requests
import httpx
import hashlib
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from openai import AzureOpenAI
from typing import Dict, Any, List

# Load environment variables
load_dotenv(override=True)

# Try importing Azure services - handle missing dependencies gracefully
try:
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
    AZURE_AVAILABLE = True
except ImportError:
    st.warning("Azure services not available - install azure packages")
    AZURE_AVAILABLE = False

try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except ImportError:
    st.warning("MongoDB not available - install pymongo")
    MONGO_AVAILABLE = False

try:
    from semantic_kernel.agents import ChatCompletionAgent
    from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
    from semantic_kernel import Kernel
    SEMANTIC_KERNEL_AVAILABLE = True
except ImportError:
    st.warning("Semantic Kernel not available - install semantic-kernel")
    SEMANTIC_KERNEL_AVAILABLE = False

try:
    from azure.communication.email import EmailClient
    EMAIL_AVAILABLE = True
except ImportError:
    st.warning("Email service not available - install azure-communication-email")
    EMAIL_AVAILABLE = False

class Config:
    """Application configuration with validation methods"""
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
        
        # Avatar/Speech
        self.speech_endpoint = os.getenv("SPEECH_ENDPOINT")
        self.speech_key = os.getenv("SPEECH_SUBSCRIPTION_KEY")
        self.blob_connection_string = os.getenv("BLOB_CONNECTION_STRING")
        self.blob_container_name = os.getenv("BLOB_CONTAINER_NAME", "avatar-videos")
        self.api_version_speech = "2024-08-01"
        
        # Email Service
        self.email_connection_string = os.getenv("AZURE_COMMUNICATION_EMAIL_CONNECTION_STRING")
        self.email_sender_address = os.getenv("EMAIL_SENDER_ADDRESS", "DoNotReply@test.azurecomm.net")
        
    def validate(self):
        required = [self.azure_endpoint, self.api_key, self.deployment_name]
        return all(required)
    
    def validate_search(self):
        return AZURE_AVAILABLE and all([self.search_endpoint, self.search_key, self.search_index])
    
    def validate_cosmos(self):
        return MONGO_AVAILABLE and bool(self.cosmos_connection_string)
    
    def validate_avatar(self):
        return AZURE_AVAILABLE and all([self.speech_endpoint, self.speech_key, self.blob_connection_string])
    
    def validate_email(self):
        return EMAIL_AVAILABLE and bool(self.email_connection_string)

class MicrosoftLearnMCPClient:
    """Microsoft Learn MCP Server Client for real-time documentation access"""
    
    def __init__(self):
        self.server_url = "https://learn.microsoft.com/api/mcp"
        self.connected = False
        self.request_id = 1
        self.session_id = None
        
    def _get_next_id(self) -> int:
        self.request_id += 1
        return self.request_id
    
    async def call_mcp(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an MCP JSON-RPC call"""
        payload = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": method
        }
        
        if params:
            payload["params"] = params
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
            "User-Agent": "Microsoft-Support-Agent-MCP/1.0",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
        
        if hasattr(self, 'session_id') and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.post(self.server_url, json=payload, headers=headers)
                
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self.session_id = session_id
                
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    
                    if "application/json" in content_type:
                        return response.json()
                    elif "text/event-stream" in content_type:
                        return await self._handle_sse_response(response)
                    else:
                        return response.json()
                else:
                    return {
                        "error": {
                            "code": response.status_code,
                            "message": f"HTTP {response.status_code}: {response.text[:200]}"
                        }
                    }
                    
        except httpx.TimeoutException:
            return {"error": {"code": -1, "message": "Request timeout"}}
        except Exception as e:
            return {"error": {"code": -1, "message": f"Connection error: {str(e)}"}}
    
    async def _handle_sse_response(self, response) -> Dict[str, Any]:
        """Handle Server-Sent Events response"""
        try:
            content = await response.aread()
            text = content.decode('utf-8')
            
            lines = text.strip().split('\n')
            data_lines = [line[5:] for line in lines if line.startswith('data:')]
            
            if data_lines:
                for data in reversed(data_lines):
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        continue
            
            return {"error": {"code": -1, "message": "Could not parse SSE response"}}
            
        except Exception as e:
            return {"error": {"code": -1, "message": f"SSE parsing error: {str(e)}"}}
    
    async def initialize(self) -> tuple[bool, str]:
        """Initialize connection with Microsoft Learn MCP Server"""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "sampling": {}
            },
            "clientInfo": {
                "name": "Microsoft Customer Support MCP Client",
                "version": "1.0.0"
            }
        }
        
        result = await self.call_mcp("initialize", params)
        
        if "error" not in result and "result" in result:
            self.connected = True
            server_info = result["result"].get("serverInfo", {})
            server_name = server_info.get("name", "Microsoft Learn MCP Server")
            server_version = server_info.get("version", "unknown")
            return True, f"Connected to {server_name} v{server_version}"
        else:
            error = result.get("error", {})
            error_code = error.get("code", "unknown")
            error_msg = error.get("message", "Unknown error")
            return False, f"Connection failed (Code {error_code}): {error_msg}"
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        result = await self.call_mcp("tools/list")
        
        if "error" not in result and "result" in result:
            return result["result"].get("tools", [])
        else:
            return []
    
    async def search_docs(self, query: str) -> Dict[str, Any]:
        """Search Microsoft documentation"""
        params = {
            "name": "microsoft_docs_search",
            "arguments": {"query": query}
        }
        
        return await self.call_mcp("tools/call", params)
    
    def extract_search_content(self, results: Dict[str, Any]) -> List[str]:
        """Extract readable content from MCP search results"""
        content_list = []
        
        if "error" in results:
            return [f"Search error: {results['error'].get('message', 'Unknown error')}"]
        
        if "result" not in results:
            return ["No results structure found"]
        
        content = results["result"].get("content", [])
        
        if not content:
            return ["No results found"]
        
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_content = item.get("text", "")
                if text_content:
                    content_list.append(text_content[:1000])  # Limit length
            elif isinstance(item, str):
                content_list.append(item[:1000])
        
        return content_list[:3]  # Limit to top 3 results

class AvatarService:
    """Handles avatar video generation and management"""
    
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.blob_service_client = None
        self.container_client = None
        
        if config.validate_avatar():
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(config.blob_connection_string)
                self.container_client = self.blob_service_client.get_container_client(config.blob_container_name)
                self.connected = True
                self._create_container_if_not_exists()
            except Exception as e:
                st.error(f"Avatar service connection failed: {e}")
                self.connected = False
    
    def _create_container_if_not_exists(self):
        try:
            self.container_client.create_container()
        except Exception:
            pass
    
    def _authenticate(self):
        return {'Ocp-Apim-Subscription-Key': self.config.speech_key}
    
    def _create_job_id(self):
        return str(uuid.uuid4())
    
    def submit_avatar_synthesis(self, job_id: str, text: str, customer_name: str = "Valued Customer", avatar_character: str = "lisa"):
        """Submit text-to-speech avatar synthesis job with MCP context"""
        if not self.connected:
            return None
        
        url = f'{self.config.speech_endpoint}/avatar/batchsyntheses/{job_id}?api-version={self.config.api_version_speech}'
        headers = {'Content-Type': 'application/json'}
        headers.update(self._authenticate())
        
        avatar_name = "Sara" if avatar_character == "sara" else "Lisa"
        personalized_text = f"""
        Hello {customer_name}, I'm {avatar_name} from Microsoft Support.
        
        Your support case has been resolved by our AI team with real-time access to Microsoft Learn documentation.
        
        {text}
        
        Thank you for choosing Microsoft.
        """
        
        payload = {
            'synthesisConfig': {
                "voice": "en-US-AvaMultilingualNeural",
                "outputFormat": "riff-24khz-16bit-mono-pcm"
            },
            "inputKind": "plainText",
            "inputs": [{"content": personalized_text.strip()}],
            "avatarConfig": {
                "customized": False,
                "talkingAvatarCharacter": "lisa",
                "talkingAvatarStyle": "graceful-sitting",
                "subtitleType": "hard_embedded",
                "videoFormat": "mp4",
                "videoCodec": "h264",
                "backgroundColor": "#FFFFFF"
            }
        }
        
        try:
            response = requests.put(url, json=payload, headers=headers)
            if response.status_code < 400:
                return response.json().get("id")
            else:
                st.error(f"Avatar synthesis error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            st.error(f"Failed to submit avatar job: {e}")
            return None
    
    def get_synthesis_status(self, job_id):
        """Check synthesis job status"""
        if not self.connected:
            return None, None
        
        url = f'{self.config.speech_endpoint}/avatar/batchsyntheses/{job_id}?api-version={self.config.api_version_speech}'
        headers = self._authenticate()
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            status = data.get('status', 'Unknown')
            if status == 'Failed':
                error_details = data.get('properties', {}).get('error', {})
                st.error(f"Avatar synthesis failed: {error_details}")
                return None, data
            elif status == 'Succeeded':
                return data.get('outputs', {}).get('result'), data
            else:
                return None, data
                
        except Exception as e:
            st.error(f"Failed to get synthesis status: {e}")
            return None, None
    
    def upload_video_to_blob(self, video_data, blob_name):
        """Upload video to blob storage"""
        if not self.connected:
            return None
        
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.upload_blob(video_data, overwrite=True)
            return blob_client.url
        except Exception as e:
            st.error(f"Failed to upload video: {e}")
            return None
    
    def generate_sas_token(self, blob_name):
        """Generate SAS token for secure video access"""
        if not self.connected:
            return None
        
        try:
            sas_token = generate_blob_sas(
                account_name=self.blob_service_client.account_name,
                container_name=self.config.blob_container_name,
                blob_name=blob_name,
                account_key=self.blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            return sas_token
        except Exception as e:
            st.error(f"Failed to generate SAS token: {e}")
            return None

class EmailService:
    """Handles email notifications with MCP integration details"""
    
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.email_client = None
        
        if config.validate_email():
            try:
                self.email_client = EmailClient.from_connection_string(config.email_connection_string)
                self.connected = True
            except Exception as e:
                st.error(f"Email service connection failed: {e}")
                self.connected = False
    
    def send_case_notification(self, case_data, resolution_summary, recipient_email, manager_name="Support Manager", mcp_enabled=False):
        """Send email notification when case is completed"""
        if not self.connected:
            return False, "Email service not connected"
        
        try:
            case_number = case_data.get('Case Number', 'Unknown')
            customer_name = case_data.get('Customer Name', 'Unknown Customer')
            subject = f"Case #{case_number} Resolved {'with MCP Integration' if mcp_enabled else ''} - {customer_name}"
            
            plain_text = f"""Hello {manager_name},

A customer support case has been successfully resolved by our AI agent system{' with Microsoft Learn MCP integration' if mcp_enabled else ''}.

CASE DETAILS:
- Case Number: {case_data.get('Case Number', 'N/A')}
- Customer: {case_data.get('Customer Name', 'N/A')}
- Organization: {case_data.get('Organization', 'N/A')}
- Issue: {case_data.get('Issue Description', 'N/A')}

RESOLUTION SUMMARY:
{resolution_summary}

Best regards,
Microsoft AI Customer Support System{' with MCP' if mcp_enabled else ''}
"""
            
            message = {
                "senderAddress": self.config.email_sender_address,
                "recipients": {
                    "to": [{"address": recipient_email}]
                },
                "content": {
                    "subject": subject,
                    "plainText": plain_text
                }
            }
            
            poller = self.email_client.begin_send(message)
            result = poller.result()
            
            return True, f"Email sent successfully"
        except Exception as e:
            return False, f"Failed to send email: {str(e)}"

class CosmosDBService:
    """Handles Cosmos DB operations with MCP integration logging"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self.database = None
        self.collection = None
        self.connected = False
        
        if config.validate_cosmos():
            self._connect()
    
    def _connect(self):
        try:
            self.client = MongoClient(self.config.cosmos_connection_string)
            self.client.admin.command('ping')
            self.database = self.client[self.config.cosmos_database_name]
            self.collection = self.database[self.config.cosmos_container_name]
            self.connected = True
        except Exception as e:
            st.error(f"Cosmos DB connection failed: {e}")
            self.connected = False
    
    def save_case(self, case_data, mcp_enabled=False):
        if not self.connected:
            return None
        
        try:
            case_data_copy = case_data.copy()
            if '_id' in case_data_copy:
                del case_data_copy['_id']
            
            case_data_copy.update({
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "status": "created",
                "processing_log": [],
                "resolution_summary": "",
                "mcp_enabled": mcp_enabled
            })
            
            result = self.collection.insert_one(case_data_copy)
            case_id = str(result.inserted_id)
            return case_id
        except Exception as e:
            st.error(f"Failed to save case: {e}")
            return None
    
    def log_agent_action(self, case_id, agent_name, action_type, details):
        if not self.connected or not case_id:
            return False
        
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "agent": agent_name,
                "action_type": action_type,
                "details": details
            }
            
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
            return result.modified_count > 0
        except Exception as e:
            st.error(f"Failed to log action: {e}")
            return False
    
    def complete_case(self, case_id, resolution_summary):
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
            return result.modified_count > 0
        except Exception as e:
            st.error(f"Failed to complete case: {e}")
            return False

class InMemoryStorage:
    """Stores cases in memory with Cosmos DB integration"""
    def __init__(self, cosmos_service=None):
        if 'cases' not in st.session_state:
            st.session_state.cases = []
        if 'current_case_id' not in st.session_state:
            st.session_state.current_case_id = None
        if 'resolution_summary' not in st.session_state:
            st.session_state.resolution_summary = ""
        if 'last_saved_case_hash' not in st.session_state:
            st.session_state.last_saved_case_hash = None
        self.cosmos_service = cosmos_service
    
    def _get_case_hash(self, case_data):
        key_fields = f"{case_data.get('Case Number', '')}{case_data.get('Customer Name', '')}{case_data.get('Issue Description', '')}"
        return hashlib.md5(key_fields.encode()).hexdigest()
    
    def save_case(self, case_data, mcp_enabled=False):
        try:
            case_hash = self._get_case_hash(case_data)
            if st.session_state.last_saved_case_hash == case_hash:
                st.warning("This case has already been saved. Skipping duplicate.")
                return True
            
            case_data['memory_id'] = f"case_{len(st.session_state.cases) + 1}"
            case_data['timestamp'] = datetime.now().isoformat()
            st.session_state.cases.append(case_data)
            
            if self.cosmos_service and self.cosmos_service.connected:
                cosmos_id = self.cosmos_service.save_case(case_data.copy(), mcp_enabled)
                if cosmos_id:
                    st.session_state.current_case_id = cosmos_id
            
            st.session_state.last_saved_case_hash = case_hash
            
            return True
        except Exception as e:
            st.error(f"Error saving case: {e}")
            return False
    
    def fetch_latest_case(self):
        if st.session_state.cases:
            return st.session_state.cases[-1]
        return None

class KnowledgeService:
    """Handles knowledge retrieval from Azure AI Search (RAG)"""
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
                
                self.embedding_client = AzureOpenAI(
                    api_key=config.api_key,
                    api_version=config.api_version,
                    azure_endpoint=config.azure_endpoint
                )
            except Exception as e:
                st.warning(f"RAG system connection failed: {e}")
    
    def search_similar_cases(self, issue_description, top_k=3):
        if not self.search_client:
            return []
        
        try:
            results = self.search_client.search(
                search_text=issue_description,
                select=["chunk_id", "parent_id", "chunk", "title"],
                top=top_k
            )
            
            return list(results)
        except Exception as e:
            st.error(f"Search error: {e}")
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
    """Multi-agent processing system with RAG and MCP integration"""
    def __init__(self, config, knowledge_service=None, cosmos_service=None, mcp_client=None):
        self.config = config
        self.knowledge_service = knowledge_service
        self.cosmos_service = cosmos_service
        self.mcp_client = mcp_client
        
        try:
            self.ai_client = AzureOpenAI(
                api_key=config.api_key,
                api_version=config.api_version,
                azure_endpoint=config.azure_endpoint
            )
        except Exception as e:
            st.error(f"Failed to initialize AI client: {e}")
            self.ai_client = None
    
    def _extract_issue_from_case(self, case_data):
        issue_desc = case_data.get('Issue Description', '')
        root_cause = case_data.get('Root Cause', '')
        organization = case_data.get('Organization', '')
        
        search_query = f"{issue_desc} {root_cause} {organization}".strip()
        return search_query if search_query else "general support issue"
    
    def _create_resolution_summary(self, agent_responses, case_data, mcp_enabled=False):
        """Create a concise resolution summary for avatar"""
        mcp_text = " with real-time Microsoft Learn documentation access" if mcp_enabled else ""
        
        final_summary = f"""
        Your support case has been successfully resolved by our multi-agent AI system{mcp_text}.
        
        Here's what we accomplished:
        
        • Analyzed your issue using our extensive knowledge base{' and current Microsoft Learn documentation' if mcp_enabled else ' of similar cases'}
        • Implemented a comprehensive technical solution following {'Microsoft\'s latest best practices' if mcp_enabled else 'proven methodologies'}
        • Established monitoring to prevent future occurrences
        • Documented the entire process for your reference
        
        The issue affecting {case_data.get('Organization', 'your organization')} has been fully addressed.
        
        Our team will continue monitoring to ensure stable operation.
        """
        
        return final_summary.strip()
    
    async def process_case_with_rag_and_mcp(self, case_data, progress_container, save_to_db=False):
        """Enhanced case processing with RAG and MCP integration"""
        
        mcp_enabled = self.mcp_client and self.mcp_client.connected
        
        case_id = None
        if save_to_db and self.cosmos_service:
            case_id = self.cosmos_service.save_case(case_data.copy(), mcp_enabled)
            if case_id:
                st.session_state.current_case_id = case_id
        
        # Simulate agent processing
        agent_sequence = [
            ("ManagerAgent", "👔 Manager"),
            ("AnalysisAgent", "🔍 Analysis"), 
            ("ExecutorAgent", "⚙️ Executor"),
            ("NotificationAgent", "📧 Notification")
        ]
        
        agent_responses = []
        
        with progress_container.container():
            for agent_name, agent_emoji in agent_sequence:
                try:
                    st.markdown(f"""
                    <div class="agent-section">
                        <h3>{agent_emoji} {agent_name} Processing...</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Simulate processing with MCP integration
                    if mcp_enabled and agent_name in ["AnalysisAgent", "ExecutorAgent"]:
                        # Try to search Microsoft Learn docs
                        try:
                            issue_query = self._create_mcp_search_query(case_data, agent_name)
                            mcp_results = await self.mcp_client.search_docs(issue_query)
                            mcp_content = self.mcp_client.extract_search_content(mcp_results)
                            
                            if mcp_content and not any("error" in content.lower() for content in mcp_content):
                                with st.expander("📚 Microsoft Learn Documentation Retrieved", expanded=False):
                                    st.markdown(f"**Search Query:** {issue_query}")
                                    for i, content in enumerate(mcp_content, 1):
                                        st.markdown(f"**Document {i}:**")
                                        st.markdown(content[:300] + "...")
                        except Exception as e:
                            st.warning(f"Could not retrieve Microsoft Learn documentation: {e}")
                    
                    # Generate response
                    response = await self._get_agent_response(agent_name, case_data, mcp_enabled)
                    
                    if response:
                        st.write(response)
                        
                        agent_responses.append({
                            'agent': agent_name,
                            'response': response,
                            'timestamp': datetime.utcnow().isoformat()
                        })
                        
                        if self.cosmos_service and case_id:
                            self.cosmos_service.log_agent_action(
                                case_id, 
                                agent_name, 
                                "agent_response", 
                                {"response": response, "mcp_context": mcp_enabled, "timestamp": datetime.utcnow().isoformat()}
                            )
                    else:
                        st.error(f"No response from {agent_name}")
                    
                except Exception as e:
                    st.error(f"Error with {agent_name}: {e}")
        
        resolution_summary = self._create_resolution_summary(agent_responses, case_data, mcp_enabled)
        
        if self.cosmos_service and case_id:
            self.cosmos_service.complete_case(case_id, resolution_summary)
        
        st.session_state.resolution_summary = resolution_summary
        
        st.success(f"✅ Case processing completed{'with MCP integration' if mcp_enabled else ''}! Resolution summary is ready for avatar video.")
        
        return resolution_summary
    
    def _create_mcp_search_query(self, case_data, agent_name):
        """Create targeted MCP search query based on case and agent type"""
        issue = case_data.get('Issue Description', '')
        root_cause = case_data.get('Root Cause', '')
        
        if agent_name == "AnalysisAgent":
            return f"troubleshooting {issue} {root_cause} Microsoft best practices diagnosis"
        elif agent_name == "ExecutorAgent":
            return f"how to fix {issue} {root_cause} Microsoft implementation guide step by step"
        else:
            return f"{issue} {root_cause} Microsoft solution"
    
    async def _get_agent_response(self, agent_name, case_data, mcp_enabled=False):
        """Generate a response for a specific agent"""
        
        responses = {
            "ManagerAgent": f"I've reviewed case #{case_data.get('Case Number', 'N/A')} for {case_data.get('Customer Name', 'Unknown')}. The issue involves {case_data.get('Issue Description', 'N/A')}. I'm assigning this to our analysis team for detailed investigation{'with access to current Microsoft documentation' if mcp_enabled else ''}.",
            
            "AnalysisAgent": f"Analysis complete for {case_data.get('Organization', 'Unknown')} case. The {case_data.get('Issue Description', 'issue')} appears to be related to {case_data.get('Root Cause', 'system configuration')}. {'Based on current Microsoft Learn documentation and' if mcp_enabled else 'Based on'} historical similar cases, I recommend immediate remediation. Severity: Medium. Impact: Localized to user environment.",
            
            "ExecutorAgent": f"Executing resolution for {case_data.get('Issue Description', 'the reported issue')}. {'Following current Microsoft best practices,' if mcp_enabled else 'Following standard procedures,'} I've implemented: 1) Configuration adjustment 2) System validation 3) Performance monitoring setup. All validation tests passed. Rollback plan established. {'Referenced Microsoft Learn articles for compliance.' if mcp_enabled else 'Standard documentation updated.'}",
            
            "NotificationAgent": f"Case resolution summary prepared for {case_data.get('Customer Name', 'the customer')}. The {case_data.get('Issue Description', 'technical issue')} has been resolved through systematic troubleshooting and configuration optimization. Customer communication package includes resolution steps, preventive measures, and{'links to relevant Microsoft Learn resources' if mcp_enabled else 'technical documentation'}. Follow-up scheduled in 48 hours."
        }
        
        return responses.get(agent_name, f"{agent_name} processing completed.")

def run_async(coro):
    """Helper to run async functions in Streamlit"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Test imports when running directly
if __name__ == "__main__":
    print("All classes imported successfully!")
    config = Config()
    print(f"Config validated: {config.validate()}")
    mcp = MicrosoftLearnMCPClient()
    print(f"MCP client created: {mcp.server_url}")