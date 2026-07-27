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
import pymongo
from pymongo import MongoClient
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# Import our new analytics system
from global_avatar_analytics import (
    GlobalAvatarAnalytics, 
    UserEngagement, 
    create_engagement_from_streamlit_data,
    get_analytics_config
)

# Load environment variables
load_dotenv(override=True)

# Security password
SECURITY_PASSWORD = "ai-gbb-2026"

# Accessing environment variables
SPEECH_ENDPOINT = os.getenv("SPEECH_ENDPOINT", "https://westus2.api.cognitive.microsoft.com")
SUBSCRIPTION_KEY = os.getenv("SPEECH_SUBSCRIPTION_KEY")
API_VERSION = os.getenv("API_VERSION", "2024-04-15-preview")

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
st.set_page_config(
    page_title="Multi-Avatar Azure AI Video Generator with Global Analytics", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize global analytics
@st.cache_resource
def initialize_analytics():
    """Initialize global analytics system"""
    config = get_analytics_config()
    if config["connection_string"] and config["enable_analytics"]:
        return GlobalAvatarAnalytics(
            connection_string=config["connection_string"],
            database_name=config["database_name"]
        )
    return None

# Initialize analytics
analytics = initialize_analytics()

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# Initialize session state for video history
if 'video_history' not in st.session_state:
    st.session_state['video_history'] = []

# Initialize session state for current session ID
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = str(uuid.uuid4())

# Password protection
if not st.session_state['authenticated']:
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h1>🔐 Secure Access Required</h1>
        <p style="font-size: 18px; color: #666;">Please enter the security password to access the Multi-Avatar Azure AI Video Generator with Global Analytics</p>
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
        <p>🤖 Powered by Azure AI Services | Secure Multi-Avatar Technology with Global Analytics</p>
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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 8px;
        margin: 10px 0;
        text-align: center;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .logout-button {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 999;
    }
    .metric-highlight {
        font-size: 2.5em;
        font-weight: bold;
        color: #0078D4;
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

# Sidebar navigation
st.sidebar.title("🤖 AI Avatar Platform")
page = st.sidebar.selectbox(
    "Navigate to:",
    ["🎬 Video Generation", "📊 Global Analytics", "👤 User Profile", "⚙️ Settings"]
)

# Avatar configurations
AVATAR_CONFIG = {
    "Binaka": {
        "character": "Binaka-half",
        "display_name": "Binaka-AI GBB Leader",
        "description": "Professional female avatar with natural expressions",
        "emoji": "👩‍💼",
        "customized": True,
        "background_url": BACKGROUND_IMAGE_Binaka_URL
    },
    "Sri": {
        "character": "sri-half",
        "display_name": "Sri-AI GBB Leader",
        "description": "Friendly and approachable avatar",
        "emoji": "👨‍💻",
        "customized": True,
        "background_url": BACKGROUND_IMAGE_sri_URL
    },
    "Mike": {
        "character": "Mike_Avatar",
        "display_name": "Mike Gaal- DN Leader",
        "description": "Professional male avatar for business presentations",
        "emoji": "👨‍💼",
        "customized": True,
        "background_url": BACKGROUND_IMAGE_mike_URL
    }
}

# Language configurations
LANGUAGE_CONFIG = {
    "English": {
        "code": "en-US",
        "voice": "Voice sync for avatar",
        "flag": "🇺🇸",
        "native_name": "English"
    },
    "Spanish": {
        "code": "es-ES",
        "voice": "Voice sync for avatar",
        "flag": "🇪🇸",
        "native_name": "Español"
    },
    "French": {
        "code": "fr-FR",
        "voice": "Voice sync for avatar",
        "flag": "🇫🇷",
        "native_name": "Français"
    },
    "German": {
        "code": "de-DE",
        "voice": "Voice sync for avatar",
        "flag": "🇩🇪",
        "native_name": "Deutsch"
    },
    "Italian": {
        "code": "it-IT",
        "voice": "Voice sync for avatar",
        "flag": "🇮🇹",
        "native_name": "Italiano"
    },
    "Portuguese": {
        "code": "pt-PT",
        "voice": "Voice sync for avatar",
        "flag": "🇵🇹",
        "native_name": "Português"
    },
    "Japanese": {
        "code": "ja-JP",
        "voice": "Voice sync for avatar",
        "flag": "🇯🇵",
        "native_name": "日本語"
    },
    "Korean": {
        "code": "ko-KR",
        "voice": "Voice sync for avatar",
        "flag": "🇰🇷",
        "native_name": "한국어"
    },
    "Chinese (Simplified)": {
        "code": "zh-CN",
        "voice": "Voice sync for avatar",
        "flag": "🇨🇳",
        "native_name": "中文(简体)"
    }
}

# Industry options for better analytics
INDUSTRY_OPTIONS = [
    "Technology", "Healthcare", "Finance", "Education", "Manufacturing", 
    "Retail", "Consulting", "Government", "Non-profit", "Other"
]

def translate_text(text, target_language):
    """Translate text using Azure OpenAI"""
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
        st.error("Azure OpenAI credentials not configured")
        return None
    
    try:
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-02-01"
        )
        
        prompt = f"Translate the following text to {target_language}. Return only the translated text without any explanations:\n\n{text}"
        
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.1
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        st.error(f"Translation failed: {str(e)}")
        return None

def _create_job_id():
    """Create a unique job ID"""
    return str(uuid.uuid4())

def submit_synthesis(job_id, text, lang_config, avatar_config):
    """Submit synthesis job to Azure"""
    url = f"{SPEECH_ENDPOINT}/avatar/batchsynthesis/{API_VERSION}"
    
    headers = {
        'Ocp-Apim-Subscription-Key': SUBSCRIPTION_KEY,
        'Content-Type': 'application/json'
    }
    
    # Create the request payload
    payload = {
        'synthesisConfig': {
            'voice': lang_config['voice']
        },
        'inputKind': 'PlainText',
        'inputs': [
            {
                'content': text
            }
        ],
        'avatarConfig': {
            'talkingAvatarCharacter': avatar_config['character'],
            'talkingAvatarStyle': 'graceful-sitting',
            'videoFormat': 'mp4',
            'videoCodec': 'h264',
            'subtitleType': 'soft_embedded',
            'backgroundColor': '#FFFFFFFF',
            'customized': avatar_config.get('customized', False)
        }
    }
    
    # Add background image if available
    if avatar_config.get('background_url'):
        payload['avatarConfig']['backgroundImage'] = avatar_config['background_url']
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 202:
            return job_id
        else:
            st.error(f"Synthesis submission failed: {response.status_code}")
            st.error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Failed to submit synthesis: {str(e)}")
        return None

def get_synthesis(job_id):
    """Get synthesis job status and result"""
    url = f"{SPEECH_ENDPOINT}/avatar/batchsynthesis/{API_VERSION}/{job_id}"
    
    headers = {
        'Ocp-Apim-Subscription-Key': SUBSCRIPTION_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
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
                
        else:
            st.error(f"Failed to get job status: {response.status_code}")
            return None, None
            
    except Exception as e:
        st.error(f"Failed to get job status: {str(e)}")
        return None, None

def save_engagement_to_analytics(username, customer_name, company_name, industry, 
                                avatar_name, language, text_input, video_url, 
                                tokens_used, processing_time=0):
    """Save engagement to global analytics system"""
    if not analytics:
        return False
    
    try:
        engagement = create_engagement_from_streamlit_data(
            username=username,
            customer_name=customer_name,
            avatar_name=avatar_name,
            language=language,
            text_input=text_input,
            video_url=video_url,
            tokens_used=tokens_used,
            company_name=company_name,
            industry=industry,
            session_id=st.session_state['session_id'],
            processing_time=processing_time
        )
        
        return analytics.save_engagement(engagement)
    
    except Exception as e:
        st.error(f"Failed to save engagement: {str(e)}")
        return False

def display_global_analytics_page():
    """Display the global analytics dashboard"""
    st.title("📊 Global AI Avatar Analytics Dashboard")
    
    if not analytics:
        st.error("Analytics system not available. Please check your configuration.")
        return
    
    # Get dashboard data
    with st.spinner("Loading global analytics..."):
        dashboard_data = analytics.get_analytics_dashboard_data()
        
        if "error" in dashboard_data:
            st.error(f"Failed to load analytics: {dashboard_data['error']}")
            return
    
    global_metrics = dashboard_data["global_metrics"]
    
    # Global metrics overview
    st.subheader("🌍 Global Platform Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="global-stats-card">
            <div class="metric-highlight">{global_metrics['total_videos_generated']:,}</div>
            <p>Total Videos Generated</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="global-stats-card">
            <div class="metric-highlight">{global_metrics['total_users']:,}</div>
            <p>Total Users</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="global-stats-card">
            <div class="metric-highlight">{global_metrics['total_tokens_consumed']:,}</div>
            <p>Total Tokens Consumed</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="global-stats-card">
            <div class="metric-highlight">{global_metrics['active_users_today']:,}</div>
            <p>Active Users Today</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Active users metrics
    st.subheader("👥 User Activity")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Active Today", global_metrics['active_users_today'])
    with col2:
        st.metric("Active This Week", global_metrics['active_users_this_week'])
    with col3:
        st.metric("Active This Month", global_metrics['active_users_this_month'])
    
    # Charts section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎭 Videos by Avatar")
        if global_metrics['videos_by_avatar']:
            avatar_df = pd.DataFrame(
                list(global_metrics['videos_by_avatar'].items()),
                columns=['Avatar', 'Videos']
            )
            fig = px.pie(avatar_df, values='Videos', names='Avatar', 
                        title="Distribution of Videos by Avatar")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🌐 Videos by Language")
        if global_metrics['videos_by_language']:
            language_df = pd.DataFrame(
                list(global_metrics['videos_by_language'].items()),
                columns=['Language', 'Videos']
            )
            fig = px.bar(language_df, x='Language', y='Videos',
                        title="Videos by Language")
            st.plotly_chart(fig, use_container_width=True)
    
    # Industry breakdown
    if dashboard_data["industry_breakdown"]:
        st.subheader("🏢 Videos by Industry")
        industry_df = pd.DataFrame(
            list(dashboard_data["industry_breakdown"].items()),
            columns=['Industry', 'Videos']
        )
        fig = px.bar(industry_df, x='Industry', y='Videos',
                    title="Engagement by Industry")
        st.plotly_chart(fig, use_container_width=True)
    
    # Growth trends
    if dashboard_data["growth_trends"]["daily_engagements"]:
        st.subheader("📈 Engagement Trends (Last 30 Days)")
        trends_data = dashboard_data["growth_trends"]["daily_engagements"]
        trends_df = pd.DataFrame(trends_data)
        trends_df.columns = ['Date', 'Engagements']
        
        fig = px.line(trends_df, x='Date', y='Engagements',
                     title="Daily Engagement Trend")
        st.plotly_chart(fig, use_container_width=True)
    
    # Top users
    st.subheader("🏆 Top Users")
    top_users = dashboard_data["top_users"]
    if top_users:
        top_users_df = pd.DataFrame(top_users)
        st.dataframe(
            top_users_df[['username', 'total_engagements', 'total_tokens', 'last_active']],
            use_container_width=True
        )
    
    # Recent activity
    st.subheader("🕒 Recent Activity")
    recent_activity = dashboard_data["recent_activity"]
    if recent_activity:
        recent_df = pd.DataFrame(recent_activity)
        st.dataframe(
            recent_df[['username', 'avatar_name', 'language', 'timestamp', 'application_source']],
            use_container_width=True
        )
    
    # Performance metrics
    performance = dashboard_data["performance_metrics"]
    if performance:
        st.subheader("⚡ Performance Metrics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Avg Processing Time", f"{performance['avg_processing_time_seconds']:.1f}s")
        with col2:
            st.metric("Avg Video Duration", f"{performance['avg_video_duration_seconds']:.1f}s")
        with col3:
            st.metric("Avg Tokens per Video", f"{performance['avg_tokens_per_video']:.1f}")

def display_user_profile_page():
    """Display user profile and personal analytics"""
    st.title("👤 User Profile & Analytics")
    
    if not analytics:
        st.error("Analytics system not available.")
        return
    
    # User input
    username = st.text_input("Enter your username to view profile:", value="")
    
    if username:
        with st.spinner("Loading user profile..."):
            user_stats = analytics.get_user_stats(username)
            
            if "error" in user_stats:
                st.error(f"Failed to load user profile: {user_stats['error']}")
                return
        
        # User metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Engagements", user_stats['total_engagements'])
        with col2:
            st.metric("Total Tokens", user_stats['total_tokens'])
        with col3:
            st.metric("Favorite Avatar", user_stats['favorite_avatar'])
        with col4:
            st.metric("Engagement Streak", f"{user_stats['engagement_streak']} days")
        
        # Additional info
        if user_stats['first_engagement']:
            st.write(f"**First Engagement:** {user_stats['first_engagement'][:10]}")
        if user_stats['last_active']:
            st.write(f"**Last Active:** {user_stats['last_active'][:10]}")
        
        # Recent engagements
        if user_stats['recent_engagements']:
            st.subheader("Recent Engagements")
            recent_df = pd.DataFrame(user_stats['recent_engagements'])
            st.dataframe(recent_df, use_container_width=True)

# Main content based on selected page
if page == "🎬 Video Generation":
    # Main title
    st.title("🎬 Multi-Avatar Azure AI Video Generator with Global Analytics")
    st.markdown("Generate personalized AI avatar videos in multiple languages with comprehensive analytics tracking")
    
    # Display global metrics summary
    if analytics:
        global_metrics = analytics.get_global_metrics()
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin: 10px 0; text-align: center;">
            <h4>🌍 Platform Global Stats</h4>
            <p><strong>{global_metrics.total_videos_generated:,}</strong> videos generated | <strong>{global_metrics.total_users:,}</strong> total users | <strong>{global_metrics.active_users_today:,}</strong> active today</p>
        </div>
        """, unsafe_allow_html=True)
    
    # User input section
    st.subheader("👤 User Information")
    
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Username*", placeholder="Enter your username")
        customer_name = st.text_input("Customer Name*", placeholder="Enter customer name")
    
    with col2:
        company_name = st.text_input("Company Name", placeholder="Enter company name (optional)")
        industry = st.selectbox("Industry", [""] + INDUSTRY_OPTIONS)
    
    # Avatar selection
    st.subheader("🎭 Choose Your Avatar")
    
    avatar_cols = st.columns(len(AVATAR_CONFIG))
    selected_avatar = None
    
    for idx, (avatar_key, avatar_info) in enumerate(AVATAR_CONFIG.items()):
        with avatar_cols[idx]:
            st.markdown(f"""
            <div class="avatar-card">
                <h4>{avatar_info['emoji']} {avatar_info['display_name']}</h4>
                <p>{avatar_info['description']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"Select {avatar_key}", key=f"avatar_{avatar_key}"):
                selected_avatar = avatar_key
                st.session_state['selected_avatar'] = avatar_key
    
    # Use session state to persist selection
    if 'selected_avatar' in st.session_state:
        selected_avatar = st.session_state['selected_avatar']
        avatar_config = AVATAR_CONFIG[selected_avatar]
        st.success(f"Selected: {avatar_config['emoji']} {avatar_config['display_name']}")
    else:
        avatar_config = AVATAR_CONFIG['Binaka']  # Default
        selected_avatar = 'Binaka'
    
    # Language selection
    st.subheader("🌐 Choose Language")
    
    selected_language = st.selectbox(
        "Select target language:",
        options=list(LANGUAGE_CONFIG.keys()),
        index=0
    )
    
    lang_config = LANGUAGE_CONFIG[selected_language]
    
    # Show selected language info
    st.markdown(f"""
    <div class="language-card">
        <h4>{lang_config['flag']} {selected_language} ({lang_config['native_name']})</h4>
        <p><strong>Voice:</strong> {lang_config['voice']}</p>
        <p><strong>Language Code:</strong> {lang_config['code']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Text input and translation
    st.subheader("✍️ Enter Your Text")
    
    input_text = st.text_area(
        "Enter the text for your avatar to speak:",
        placeholder="Enter your message here...",
        height=100,
        max_chars=1000
    )
    
    # Character and token count
    char_count = len(input_text)
    words = len(input_text.split()) if input_text else 0
    tokens = int(words * 0.75)  # Rough estimation
    max_chars = 1000
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Characters:** {char_count}/{max_chars}")
    with col2:
        st.write(f"**Words:** {words}")
    with col3:
        st.write(f"**Estimated Tokens:** {tokens}")
    
    # Progress bar for character limit
    progress_value = min(char_count / max_chars, 1.0)
    st.progress(progress_value)
    
    if char_count > max_chars:
        st.error(f"Text is too long! Maximum {max_chars} characters allowed.")
    
    # Translation section
    if selected_language != "English" and input_text:
        st.subheader("🔄 Translation")
        
        if st.button("Translate to " + selected_language):
            with st.spinner(f"Translating to {selected_language}..."):
                translated = translate_text(input_text, lang_config['native_name'])
                if translated:
                    st.session_state['translated_text'] = translated
                    st.success("Translation completed!")
                else:
                    st.error("Translation failed. Please try again.")
        
        if 'translated_text' in st.session_state:
            st.markdown(f"""
            <div class="translated-text">
                <h4>Translated Text ({selected_language}):</h4>
                <p>{st.session_state['translated_text']}</p>
            </div>
            """, unsafe_allow_html=True)
    
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
            start_time = time.time()
            
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
                            processing_time = time.time() - start_time
                            
                            st.success(f"{selected_language} {avatar_config['display_name']} avatar video generated successfully!")
                            progress_bar.progress(1.0)
                            status_text.text("Completed!")

                            # Save engagement to analytics
                            if analytics:
                                engagement_saved = save_engagement_to_analytics(
                                    username=username,
                                    customer_name=customer_name,
                                    company_name=company_name,
                                    industry=industry,
                                    avatar_name=avatar_config['display_name'],
                                    language=selected_language,
                                    text_input=final_text,
                                    video_url=download_url,
                                    tokens_used=tokens,
                                    processing_time=processing_time
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
                                    "timestamp": datetime.now().isoformat(),
                                    "processing_time": f"{processing_time:.1f}s"
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
    
    # User engagement statistics
    if username and analytics:
        st.subheader("Your Personal Statistics")
        user_stats = analytics.get_user_stats(username)
        
        if not user_stats.get("error"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div class="stats-card">
                    <h3>{user_stats['total_engagements']}</h3>
                    <p>Total Engagements</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="stats-card">
                    <h3>{user_stats['total_tokens']}</h3>
                    <p>Total Tokens Used</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                avg_tokens = user_stats['total_tokens'] / max(1, user_stats['total_engagements'])
                st.markdown(f"""
                <div class="stats-card">
                    <h3>{avg_tokens:.1f}</h3>
                    <p>Avg Tokens per Video</p>
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
                    st.write(f"**Processing Time:** {video.get('processing_time', 'N/A')}")
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
        if 'selected_avatar' in st.session_state:
            del st.session_state['selected_avatar']
        st.session_state['video_history'] = []
        st.session_state['session_id'] = str(uuid.uuid4())
        st.success("Session reset successfully.")

elif page == "📊 Global Analytics":
    display_global_analytics_page()

elif page == "👤 User Profile":
    display_user_profile_page()

elif page == "⚙️ Settings":
    st.title("⚙️ Settings & Configuration")
    
    st.subheader("Analytics Configuration")
    if analytics:
        st.success("✅ Global Analytics System: Connected")
        
        # Analytics controls
        st.subheader("Analytics Controls")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Refresh Analytics Cache"):
                st.cache_resource.clear()
                st.success("Analytics cache refreshed!")
        
        with col2:
            test_username = st.text_input("Test Username for Reset:")
            if st.button("⚠️ Reset User Metrics", type="secondary"):
                if test_username and analytics:
                    success = analytics.reset_user_metrics(test_username)
                    if success:
                        st.success(f"Metrics reset for user: {test_username}")
                    else:
                        st.error("Failed to reset user metrics")
                else:
                    st.warning("Please enter a username")
    else:
        st.error("❌ Global Analytics System: Not Connected")
        st.write("Please check your AZCOSMOS_CONNSTR environment variable")
    
    st.subheader("System Information")
    st.write(f"**Session ID:** {st.session_state['session_id']}")
    st.write(f"**Speech Endpoint:** {SPEECH_ENDPOINT}")
    st.write(f"**API Version:** {API_VERSION}")
    
    # Environment status
    st.subheader("Environment Status")
    env_status = {
        "SPEECH_SUBSCRIPTION_KEY": "✅ Configured" if SUBSCRIPTION_KEY else "❌ Missing",
        "AZURE_OPENAI_ENDPOINT": "✅ Configured" if AZURE_OPENAI_ENDPOINT else "❌ Missing",
        "AZURE_OPENAI_API_KEY": "✅ Configured" if AZURE_OPENAI_API_KEY else "❌ Missing",
        "AZCOSMOS_CONNSTR": "✅ Configured" if COSMOS_CONNECTION_STRING else "❌ Missing"
    }
    
    for key, status in env_status.items():
        st.write(f"**{key}:** {status}")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>Powered by Azure AI Services | Multi-Avatar Technology with Global Analytics</p>
    <p><strong>Token Calculation:</strong> ~0.75 tokens per word (billing estimation) | <strong>Engagement:</strong> Each video = 1 engagement</p>
    <p><strong>Contact & Feedback:</strong> <a href="mailto:ganac@microsoft.com" style="color: #0078D4; text-decoration: none;">ganac@microsoft.com</a> (AI-GBB Team)</p>
</div>
""", unsafe_allow_html=True)
