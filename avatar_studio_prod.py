import streamlit as st
import json
import logging
import os
import sys
import time
import uuid
import requests
from datetime import datetime, timedelta, timezone
import base64
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential
import pymongo
from pymongo import MongoClient

# Load environment variables
load_dotenv(override=True)

# Security password
SECURITY_PASSWORD = "ai-gbb-2026"

# Accessing environment variables
# For Managed Identity auth, SPEECH_ENDPOINT must be the custom subdomain:
#   https://<resource-name>.cognitiveservices.azure.com
# Alternatively, set SPEECH_RESOURCE_NAME and the endpoint will be auto-constructed.
_speech_resource_name = os.getenv("SPEECH_RESOURCE_NAME", "")
_speech_endpoint_raw = os.getenv("SPEECH_ENDPOINT", "")

if _speech_resource_name and "cognitiveservices.azure.com" not in _speech_endpoint_raw:
    # Auto-construct the custom subdomain endpoint from the resource name
    SPEECH_ENDPOINT = f"https://{_speech_resource_name}.cognitiveservices.azure.com"
else:
    SPEECH_ENDPOINT = _speech_endpoint_raw

API_VERSION = os.getenv("API_VERSION", "2024-08-01")

# Managed Identity credential (replaces key-based auth)
# AZURE_TENANT_ID must match the tenant of the Speech resource.
_azure_tenant_id = os.getenv("AZURE_TENANT_ID", "")
_credential = DefaultAzureCredential()

def _get_speech_token():
    """Obtain a Bearer token for Azure Cognitive Services via Managed Identity."""
    token = _credential.get_token("https://cognitiveservices.azure.com/.default")
    return token.token
# Avatar-specific background images
BACKGROUND_IMAGE_Binaka_URL = os.getenv("BACKGROUND_IMAGE_Binaka_URL")
BACKGROUND_IMAGE_sri_URL = os.getenv("BACKGROUND_IMAGE_sri_URL") 
BACKGROUND_IMAGE_mike_URL = os.getenv("BACKGROUND_IMAGE_mike_URL")

# Azure OpenAI for translation
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Azure Cosmos DB MongoDB configuration
COSMOS_CONNECTION_STRING = os.getenv("AZCOSMOS_CONNSTR")
COSMOS_DATABASE_NAME = os.getenv("AZCOSMOS_DATABASE_NAME_Batch", "avatarbatch")
COSMOS_CONTAINER_NAME = os.getenv("AZCOSMOS_CONTAINER_NAME_batch", "avatarbatch")

# Set up the page configuration
st.set_page_config(page_title="Multi-Avatar Azure AI Video Generator", layout="wide")

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# Password protection
if not st.session_state['authenticated']:
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h1>🔐 Secure Access Required</h1>
        <p style="font-size: 18px; color: #666;">Please enter the security password to access the Multi-Avatar Azure AI Video Generator</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Center the password input
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("Enter Password:", type="password", placeholder="Security password required")
        
        if st.button("🚀 Access Application", type="primary"):
            if password == SECURITY_PASSWORD:
                st.session_state['authenticated'] = True
                st.success("✅ Access granted! Redirecting...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Incorrect password. Please try again.")
    
    st.markdown("""
    <div style="text-align: center; margin-top: 50px; color: #888;">
        <p>🤖 Powered by Azure AI Services | Secure Multi-Avatar Technology</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.stop()

# Custom CSS
st.markdown(
    """
    <style>
    .stApp {
        background-color: #E5F8FF;
        background-image: linear-gradient(to right, #B2FFEC, #D9F4FF);
    }
    .stTextInput>div>div>input {
        background-color: #FFFFFF;
        color: #000000;
    }
    h1 {
        font-size: 2em;
        line-height: 1.2;
    }
    .language-card {
        background: white;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #0078D4;
    }
    .avatar-card {
        background: white;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #ff6b35;
    }
    .translated-text {
        background: #f0f8ff;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #4CAF50;
        margin: 10px 0;
    }
    .avatar-info {
        background: #fff3cd;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 10px 0;
    }
    .stats-card {
        background: #e8f5e8;
        padding: 20px;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 10px 0;
        text-align: center;
    }
    .global-stats-card {
        background: #f0f4ff;
        padding: 20px;
        border-radius: 8px;
        border-left: 4px solid #6c5ce7;
        margin: 10px 0;
        text-align: center;
    }
    .logout-button {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 999;
    }
    .stButton > button {
        white-space: nowrap !important;
        min-width: 100px !important;
        padding: 0.25rem 0.75rem !important;
        font-size: 0.875rem !important;
    }
    div[data-testid="column"]:nth-child(2) .stButton > button {
        width: 100% !important;
        white-space: nowrap !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Add logout button in top right corner
col1, col2 = st.columns([9, 1])
with col2:
    if st.button("🔓 Logout", key="logout_btn", help="Logout from application"):
        st.session_state['authenticated'] = False
        st.rerun()

# Avatar configurations
AVATAR_CONFIG = {
    "Binaka": {
        "character": "Binaka-half",
        "display_name": "Binaka-AI GBB Leader",
        "description": "Professional female avatar with natural expressions",
        "emoji": "👩‍💼",
        "customized": True,
        "style": "",
        "use_built_in_voice": True,   # voice sync: uses the voice the avatar was trained with
        "background_url": BACKGROUND_IMAGE_Binaka_URL
    },
    "Sri": {
        "character": "sri-half",
        "display_name": "Sri-AI GBB Leader",
        "description": "Friendly and approachable avatar",
        "emoji": "👨‍💻",
        "customized": True,
        "style": "",
        "use_built_in_voice": True,
        "background_url": BACKGROUND_IMAGE_sri_URL
    },
    "Mike": {
        "character": "Mike_Avatar",
        "display_name": "Mike Gaal- DN Leader",
        "description": "Professional male avatar for business presentations",
        "emoji": "👨‍💼",
        "customized": True,
        "style": "",
        "use_built_in_voice": True,
        "background_url": BACKGROUND_IMAGE_mike_URL
    }
}

# Language configurations
LANGUAGE_CONFIG = {
    "English": {
        "code": "en-US",
        "voice": "en-US-AvaMultilingualNeural",
        "flag": "🇺🇸",
        "native_name": "English"
    },
    "Spanish": {
        "code": "es-ES",
        "voice": "es-ES-ElviraNeural",
        "flag": "🇪🇸",
        "native_name": "Español"
    },
    "French": {
        "code": "fr-FR",
        "voice": "fr-FR-DeniseNeural",
        "flag": "🇫🇷",
        "native_name": "Français"
    },
    "German": {
        "code": "de-DE",
        "voice": "de-DE-KatjaNeural",
        "flag": "🇩🇪",
        "native_name": "Deutsch"
    },
    "Italian": {
        "code": "it-IT",
        "voice": "it-IT-ElsaNeural",
        "flag": "🇮🇹",
        "native_name": "Italiano"
    },
    "Portuguese": {
        "code": "pt-BR",
        "voice": "pt-BR-FranciscaNeural",
        "flag": "🇧🇷",
        "native_name": "Português"
    },
    "Dutch": {
        "code": "nl-NL",
        "voice": "nl-NL-ColetteNeural",
        "flag": "🇳🇱",
        "native_name": "Nederlands"
    },
    "Russian": {
        "code": "ru-RU",
        "voice": "ru-RU-SvetlanaNeural",
        "flag": "🇷🇺",
        "native_name": "Русский"
    },
    "Japanese": {
        "code": "ja-JP",
        "voice": "ja-JP-NanamiNeural",
        "flag": "🇯🇵",
        "native_name": "日本語"
    },
    "Korean": {
        "code": "ko-KR",
        "voice": "ko-KR-SunHiNeural",
        "flag": "🇰🇷",
        "native_name": "한국어"
    },
    "Chinese": {
        "code": "zh-CN",
        "voice": "zh-CN-XiaoxiaoNeural",
        "flag": "🇨🇳",
        "native_name": "中文"
    },
    "Hindi": {
        "code": "hi-IN",
        "voice": "hi-IN-SwaraNeural",
        "flag": "🇮🇳",
        "native_name": "हिन्दी"
    },
    "Arabic": {
        "code": "ar-SA",
        "voice": "ar-SA-ZariyahNeural",
        "flag": "🇸🇦",
        "native_name": "العربية"
    }
}

# Initialize session state for video history
if 'video_history' not in st.session_state:
    st.session_state['video_history'] = []

# Connect to Cosmos DB MongoDB
mongo_collection = None
if COSMOS_CONNECTION_STRING:
    try:
        mongo_client = MongoClient(COSMOS_CONNECTION_STRING)
        mongo_db = mongo_client[COSMOS_DATABASE_NAME]
        mongo_collection = mongo_db[COSMOS_CONTAINER_NAME]
        logging.info("Connected to Cosmos DB MongoDB successfully")
    except Exception as e:
        st.error(f"Failed to connect to Cosmos DB: {str(e)}")
        logging.error(f"Cosmos DB connection error: {str(e)}")

# Functions
def calculate_tokens(text):
    """Calculate tokens based on word count with adjustment factor."""
    words = len(text.split())
    tokens = int(words * 0.75)  # Approximation for tokens
    return tokens, words

def get_translation_client():
    """Get Azure OpenAI client for translation."""
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
        st.error("Azure OpenAI configuration is missing. Please check your environment variables.")
        return None
    
    try:
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-02-01"
        )
        return client
    except Exception as e:
        st.error(f"Failed to initialize Azure OpenAI client: {str(e)}")
        return None

def translate_text(text, target_language, client):
    """Translate text using Azure OpenAI."""
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": f"You are a professional translator. Translate the following text to {target_language}. Keep the tone professional and maintain the original meaning. Only return the translated text, nothing else."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            max_tokens=2000,
            temperature=0.3
        )
        
        translated_text = response.choices[0].message.content.strip()
        return translated_text
    except Exception as e:
        st.error(f"Translation failed: {str(e)}")
        return None

def save_engagement_to_cosmos(username, customer_name, avatar_name, language, text, video_url):
    """Save engagement data to Cosmos DB."""
    if mongo_collection is None:
        return False
    
    try:
        tokens, words = calculate_tokens(text)
        engagement_data = {
            "id": str(uuid.uuid4()),
            "username": username,
            "customer_name": customer_name,
            "avatar_name": avatar_name,
            "language": language,
            "text": text,
            "video_url": video_url,
            "tokens": tokens,
            "words": words,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "created_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        }
        
        result = mongo_collection.insert_one(engagement_data)
        return result.inserted_id is not None
    except Exception as e:
        st.error(f"Failed to save engagement: {str(e)}")
        return False

def get_user_stats(username):
    """Get user engagement statistics."""
    if mongo_collection is None:
        return {"engagements": 0, "total_tokens": 0}
    
    try:
        pipeline = [
            {"$match": {"username": username}},
            {"$group": {
                "_id": "$username",
                "engagements": {"$sum": 1},
                "total_tokens": {"$sum": "$tokens"}
            }}
        ]
        
        result = list(mongo_collection.aggregate(pipeline))
        if result:
            return {
                "engagements": result[0]["engagements"],
                "total_tokens": result[0]["total_tokens"]
            }
        else:
            return {"engagements": 0, "total_tokens": 0}
    except Exception as e:
        st.error(f"Failed to get user stats: {str(e)}")
        return {"engagements": 0, "total_tokens": 0}

def get_global_stats():
    """Get global engagement statistics."""
    if mongo_collection is None:
        return {
            "total_engagements": 0,
            "total_multi_lingua_videos": 0,
            "total_customers": 0
        }
    
    try:
        # Total engagements
        total_engagements = mongo_collection.count_documents({})
        
        # Total multi-lingua videos (non-English videos)
        total_multi_lingua_videos = mongo_collection.count_documents({
            "language": {"$ne": "English"}
        })
        
        # Total unique customers
        unique_customers = mongo_collection.distinct("customer_name")
        total_customers = len(unique_customers)
        
        return {
            "total_engagements": total_engagements,
            "total_multi_lingua_videos": total_multi_lingua_videos,
            "total_customers": total_customers
        }
    except Exception as e:
        st.error(f"Failed to get global stats: {str(e)}")
        return {
            "total_engagements": 0,
            "total_multi_lingua_videos": 0,
            "total_customers": 0
        }

def _authenticate():
    """Return auth headers using Managed Identity Bearer token."""
    return {
        'Authorization': f'Bearer {_get_speech_token()}'
    }

def _create_job_id():
    """Generate a unique job ID."""
    return str(uuid.uuid4())

def submit_synthesis(job_id, input_text, lang_config, avatar_config):
    """Submit text to avatar synthesis."""
    endpoint = SPEECH_ENDPOINT.rstrip('/')
    url = f'{endpoint}/avatar/batchsyntheses/{job_id}?api-version={API_VERSION}'
    
    header = {
        'Content-Type': 'application/json',
        **_authenticate()
    }

    # Fixed video settings
    video_format = "mp4"
    video_codec = "h264"  # hevc, h264 or vp9 (vp9 required for transparent background)
    bg_color = "#FFFFFFFF"  # RGBA format; use 'transparent' for transparent background

    payload = {
        'synthesisConfig': {
            "voice": lang_config['voice'],
        },
        # Add custom voice name -> deployment ID mappings here if needed
        'customVoices': {},
        "inputKind": "PlainText",  # PlainText or SSML
        "inputs": [{"content": input_text.strip()}],
        "avatarConfig": {
            "customized": avatar_config['customized'],
            "talkingAvatarCharacter": avatar_config['character'],
            "talkingAvatarStyle": avatar_config.get('style', ""),
            "videoFormat": video_format,
            "videoCodec": video_codec,
            "subtitleType": "soft_embedded",
            "backgroundColor": bg_color,
            # useBuiltInVoice: True enables voice sync for custom avatars trained with voice sync
            "useBuiltInVoice": avatar_config.get('use_built_in_voice', True)
        }
    }

    # Remove talkingAvatarStyle if empty (not required for custom avatars)
    if not payload["avatarConfig"]["talkingAvatarStyle"]:
        del payload["avatarConfig"]["talkingAvatarStyle"]
    
    # Add avatar-specific background image if provided
    if avatar_config.get('background_url') and avatar_config['background_url'].strip():
        payload["avatarConfig"]["backgroundImage"] = avatar_config['background_url']

    try:
        response = requests.put(url, json=payload, headers=header, timeout=30)
        
        if response.status_code < 400:
            response_json = response.json()
            return response_json.get("id")
        else:
            st.error(f'Failed to submit synthesis job. Status: {response.status_code}')
            st.error(f'Response: {response.text}')
            return None
            
    except Exception as e:
        st.error(f'Request failed: {str(e)}')
        return None

def get_synthesis(job_id):
    """Check synthesis job status"""
    endpoint = SPEECH_ENDPOINT.rstrip('/')
    url = f'{endpoint}/avatar/batchsyntheses/{job_id}?api-version={API_VERSION}'
    header = _authenticate()

    try:
        response = requests.get(url, headers=header, timeout=30)
        response.raise_for_status()
        response_data = response.json()

        if response_data.get('status') == 'Succeeded':
            outputs = response_data.get('outputs', {})
            result_url = outputs.get('result')
            return result_url, response_data
        elif response_data.get('status') == 'Failed':
            error_detail = response_data.get('error', {})
            if isinstance(error_detail, dict):
                error_msg = f"Code: {error_detail.get('code', 'Unknown')}, Message: {error_detail.get('message', 'No details')}"
            else:
                error_msg = str(error_detail)
            st.error(f"Synthesis failed: {error_msg}")
            return None, None
        else:
            return None, None
            
    except Exception as e:
        st.error(f"Failed to get job status: {str(e)}")
        return None, None

# Validation
if not SPEECH_ENDPOINT:
    st.error(
        "Speech endpoint not configured. Set one of the following in your .env file:\n\n"
        "**Option A** — provide the full custom subdomain URL:\n"
        "`SPEECH_ENDPOINT=https://<your-resource-name>.cognitiveservices.azure.com`\n\n"
        "**Option B** — provide just the resource name and the URL is auto-constructed:\n"
        "`SPEECH_RESOURCE_NAME=<your-resource-name>`"
    )
    st.stop()

# Token auth requires a custom subdomain endpoint, not a regional one.
if "cognitiveservices.azure.com" not in SPEECH_ENDPOINT:
    st.error(
        "**Invalid SPEECH_ENDPOINT for Managed Identity authentication.**\n\n"
        "Regional endpoints (e.g. `https://westus2.api.cognitive.microsoft.com`) "
        "only support API key authentication.\n\n"
        "Fix by setting one of these in your .env file:\n"
        "- `SPEECH_ENDPOINT=https://avatartwin.cognitiveservices.azure.com/`\n"
        "- `SPEECH_RESOURCE_NAME=<your-resource-name>`"
    )
    st.stop()

# Main content
st.title("Elevate Your Sales Pitch: Create Personalized AI-Driven Videos with the Help of AI Avatar, Your AI GBB Agent")
st.markdown("Create personalized avatar videos with voice synchronization in multiple languages using Azure AI Services")

# Sidebar
with st.sidebar:
    st.header("User Information")
    username = st.text_input("Username", value="")
    industry_vertical = st.selectbox("Industry Vertical", ["education", "healthcare", "manufacturing", "telecom", "sdp", "finance", "other"])
    customer_name = st.text_input("Customer Name", value="")
    date = st.date_input("Date", value=datetime.now().date())
    
    st.markdown("---")
    
    # Avatar selection
    st.header("Avatar Selection")
    selected_avatar = st.selectbox(
        "Choose Avatar",
        options=list(AVATAR_CONFIG.keys()),
        format_func=lambda x: f"{AVATAR_CONFIG[x]['emoji']} {AVATAR_CONFIG[x]['display_name']}"
    )
    
    # Display avatar info
    avatar_config = AVATAR_CONFIG[selected_avatar]
    background_status = "✅ Custom Background" if avatar_config.get('background_url') else "❌ No Background"
    st.markdown(f"""
    <div class="avatar-card">
        <strong>{avatar_config['emoji']} Selected Avatar:</strong> {avatar_config['display_name']}<br>
        <strong>Character:</strong> {avatar_config['character']}<br>
        <strong>Description:</strong> {avatar_config['description']}<br>
        <strong>Type:</strong> {'Custom' if avatar_config['customized'] else 'Standard'}<br>
        <strong>Background:</strong> {background_status}
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Language selection
    st.header("Language Settings")
    selected_language = st.selectbox(
        "Choose Language",
        options=list(LANGUAGE_CONFIG.keys()),
        format_func=lambda x: f"{LANGUAGE_CONFIG[x]['flag']} {x} ({LANGUAGE_CONFIG[x]['native_name']})"
    )
    
    # Display language info
    lang_config = LANGUAGE_CONFIG[selected_language]
    st.markdown(f"""
    <div class="language-card">
        <strong>{lang_config['flag']} Selected Language:</strong> {selected_language}<br>
        <strong>Voice:</strong> {lang_config['voice']}<br>
        <strong>Native Name:</strong> {lang_config['native_name']}
    </div>
    """, unsafe_allow_html=True)

# Avatar information display
st.markdown(f"""
<div class="avatar-info">
    <strong>{avatar_config['emoji']} Current Avatar: {avatar_config['display_name']}</strong><br>
    <strong>Character:</strong> {avatar_config['character']}<br>
    <strong>Features:</strong> Built-in voice synchronization, multilingual support<br>
    <strong>Technology:</strong> Azure AI Avatar with neural voice synthesis
</div>
""", unsafe_allow_html=True)

# Default text generation
if username and industry_vertical and customer_name:
    default_input_text = (
        f"Welcome {customer_name}! I'm {avatar_config['display_name']}, your AI partner from the Global Black Belt AI Team at Microsoft. "
        "We're thrilled that you've chosen to explore AI solutions with us. Our team is eager to collaborate with you to build cutting-edge AI solutions using Microsoft Azure AI services, along with our trusted partners. "
        "Let's embark on this journey together and transform your business with the power of AI. This personalized avatar is here to assist you and provide all the information you need."
    )
else:
    default_input_text = f"Hi, I'm {avatar_config['display_name']}, your AI partner from the Global Black Belt AI Team at Microsoft."

# Input text
st.subheader("Input Text (English)")
input_text = st.text_area("Enter your message in English:", value=default_input_text, height=150)

# Character count and token calculation
char_count = len(input_text)
tokens, words = calculate_tokens(input_text)
max_chars = 3000

col1, col2, col3 = st.columns(3)
with col1:
    st.caption(f"Characters: {char_count}/{max_chars}")
with col2:
    st.caption(f"Words: {words}")
with col3:
    st.caption(f"Estimated Tokens: {tokens}")

if char_count > max_chars:
    st.error(f"Text is too long. Please reduce by {char_count - max_chars} characters.")

# Translation section
if input_text and selected_language != "English":
    st.subheader(f"Translation to {selected_language}")
    
    translation_client = get_translation_client()
    if translation_client:
        if st.button("Translate Text", type="secondary"):
            with st.spinner(f"Translating to {selected_language}..."):
                translated_text = translate_text(input_text, selected_language, translation_client)
                if translated_text:
                    st.session_state['translated_text'] = translated_text
                    st.success(f"✅ Text translated to {selected_language} successfully!")
        
        if 'translated_text' in st.session_state:
            st.markdown(f"""
            <div class="translated-text">
                <strong>{lang_config['flag']} Translated Text ({selected_language}):</strong><br>
                {st.session_state['translated_text']}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Translation service is not available. Please check Azure OpenAI configuration.")

# Display current settings
with st.expander("Current Settings", expanded=False):
    st.write(f"**Avatar:** {avatar_config['emoji']} {avatar_config['display_name']} ({avatar_config['character']})")
    st.write(f"**Background Image:** {'✅ Custom' if avatar_config.get('background_url') else '❌ Default'}")
    if avatar_config.get('background_url'):
        st.write(f"**Background URL:** {avatar_config['background_url']}")
    st.write(f"**Language:** {selected_language} {lang_config['flag']}")
    st.write(f"**Voice:** {lang_config['voice']}")
    st.write(f"**Video Format:** MP4 (H.264)")
    st.write(f"**Background Color:** White")
    st.write(f"**Built-in Voice:** Enabled")
    st.write(f"**Text Length:** {char_count} characters")
    st.write(f"**Estimated Tokens:** {tokens}")

# Submit button
final_text = input_text
if selected_language != "English" and 'translated_text' in st.session_state:
    final_text = st.session_state['translated_text']

if st.button(f"Generate {avatar_config['display_name']} {selected_language} Video", type="primary", disabled=(char_count > max_chars)):
    if not username or not input_text or not customer_name:
        st.warning("Please enter username, text, and customer name.")
    elif char_count > max_chars:
        st.error(f"Text is too long. Maximum {max_chars} characters allowed.")
    elif selected_language != "English" and 'translated_text' not in st.session_state:
        st.warning("Please translate the text first before generating the video.")
    else:
        job_id = _create_job_id()
        
        st.info(f"Creating {selected_language} {avatar_config['display_name']} avatar video with voice synchronization...")
        
        # Submit synthesis job
        submitted_job_id = submit_synthesis(job_id, final_text, lang_config, avatar_config)
        if submitted_job_id:
            st.info(f"Job submitted successfully. ID: {submitted_job_id}")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            with st.spinner(f"Processing {selected_language} {avatar_config['display_name']} avatar video..."):
                max_attempts = 60
                attempts = 0
                video_content = None
                
                while attempts < max_attempts:
                    progress = (attempts + 1) / max_attempts
                    progress_bar.progress(progress)
                    status_text.text(f"Processing... {attempts + 1}/{max_attempts}")
                    
                    download_url, response_data = get_synthesis(submitted_job_id)
                    
                    if download_url and response_data:
                        st.success(f"{selected_language} {avatar_config['display_name']} avatar video generated successfully!")
                        progress_bar.progress(1.0)
                        status_text.text("Completed!")

                        # Save engagement to Cosmos DB
                        engagement_saved = save_engagement_to_cosmos(
                            username, customer_name, avatar_config['display_name'], 
                            selected_language, final_text, download_url
                        )
                        
                        if engagement_saved:
                            st.success("Engagement data saved successfully!")
                        
                        # Download and display video
                        try:
                            with requests.get(download_url, stream=True) as r:
                                r.raise_for_status()
                                video_content = b''
                                for chunk in r.iter_content(chunk_size=8192):
                                    video_content += chunk

                            st.session_state['video_history'].append({
                                "avatar": avatar_config['display_name'],
                                "language": selected_language,
                                "flag": lang_config['flag'],
                                "emoji": avatar_config['emoji'],
                                "url": download_url,
                                "tokens": tokens,
                                "words": words,
                                "timestamp": datetime.now().isoformat()
                            })

                            # Display results
                            col1, col2 = st.columns([1, 1])
                            
                            with col1:
                                if video_content:
                                    video_name = f"{username}_{customer_name}_{avatar_config['display_name']}_{selected_language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                                    st.download_button(
                                        label=f"Download {avatar_config['display_name']} {selected_language} Video",
                                        data=video_content,
                                        file_name=video_name,
                                        mime='video/mp4',
                                        type="primary"
                                    )
                            
                            with col2:
                                st.video(download_url)
                            
                        except Exception as e:
                            st.error(f"Error processing video: {str(e)}")

                        break
                    
                    attempts += 1
                    if attempts < max_attempts:
                        time.sleep(5)
                
                if attempts >= max_attempts:
                    st.error("Processing timed out. Please try again.")
        else:
            st.error("Failed to submit synthesis job.")

# Global engagement statistics
if mongo_collection is not None:
    st.subheader("Global Platform Statistics")
    global_stats = get_global_stats()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="global-stats-card">
            <h3>🌍 {global_stats['total_engagements']}</h3>
            <p>Total Engagements</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="global-stats-card">
            <h3>🌐 {global_stats['total_multi_lingua_videos']}</h3>
            <p>Multi-Lingua Videos</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="global-stats-card">
            <h3>🏢 {global_stats['total_customers']}</h3>
            <p>Total Customers</p>
        </div>
        """, unsafe_allow_html=True)



# Video history
st.subheader("Session Video History")
if st.session_state['video_history']:
    for i, video in enumerate(reversed(st.session_state['video_history'])):
        with st.expander(f"{video['emoji']} {video['flag']} {video['avatar']} {video['language']} Video {len(st.session_state['video_history']) - i}", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Avatar:** {video['emoji']} {video['avatar']}")
                st.write(f"**Language:** {video['flag']} {video['language']}")
                st.write(f"**Words:** {video['words']}")
                st.write(f"**Tokens:** {video['tokens']}")
                st.write(f"**Created:** {video.get('timestamp', 'Unknown')}")
                st.markdown(f"[Video Link]({video['url']})")
            
            with col2:
                st.video(video['url'])
else:
    st.info("No videos generated in this session yet.")

# Reset session
if st.button("Reset Session"):
    if 'translated_text' in st.session_state:
        del st.session_state['translated_text']
    st.session_state['video_history'] = []
    st.success("Session reset successfully.")

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>Powered by Azure AI Services | Multi-Avatar Technology with Analytics</p>
    <p><strong>Token Calculation:</strong> ~0.75 tokens per word (billing estimation) | <strong>Engagement:</strong> Each video = 1 engagement</p>
    <p><strong>Contact & Feedback:</strong> <a href="mailto:ganac@microsoft.com" style="color: #0078D4; text-decoration: none;">ganac@microsoft.com</a> (AI-GBB Team)</p>
</div>
""", unsafe_allow_html=True)