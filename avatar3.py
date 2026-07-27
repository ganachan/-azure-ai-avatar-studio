import streamlit as st
import json
import logging
import os
import sys
import time
import uuid
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Try to import OpenAI (optional)
try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the page configuration
st.set_page_config(page_title="Azure AI Avatar - Microsoft Reference", layout="wide")

# Configuration - exactly matching Microsoft reference
SPEECH_ENDPOINT = os.getenv('SPEECH_ENDPOINT', "https://westus2.api.cognitive.microsoft.com")
PASSWORDLESS_AUTHENTICATION = False
API_VERSION = "2024-04-15-preview"

# Background images (optional)
BACKGROUND_IMAGE_BINAKA_URL = os.getenv("BACKGROUND_IMAGE_Binaka_URL")
BACKGROUND_IMAGE_SRI_URL = os.getenv("BACKGROUND_IMAGE_sri_URL") 
BACKGROUND_IMAGE_MIKE_URL = os.getenv("BACKGROUND_IMAGE_mike_URL")

# Azure OpenAI for translation (optional)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Authentication function - exactly like Microsoft reference
def _authenticate():
    if PASSWORDLESS_AUTHENTICATION:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        token = credential.get_token('https://cognitiveservices.azure.com/.default')
        return {'Authorization': f'Bearer {token.token}'}
    else:
        SUBSCRIPTION_KEY = os.getenv("SUBSCRIPTION_KEY", os.getenv("SPEECH_SUBSCRIPTION_KEY"))
        return {'Ocp-Apim-Subscription-Key': SUBSCRIPTION_KEY}

# Custom CSS
st.markdown(
    """
    <style>
    .stApp {
        background-color: #E5F8FF;
        background-image: linear-gradient(to right, #B2FFEC, #D9F4FF);
    }
    .language-card {
        background: white;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #0078D4;
    }
    .translated-text {
        background: #f0f8ff;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #4CAF50;
        margin: 10px 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Avatar configurations - All using built-in voice sync
CUSTOM_AVATARS = {
    "Binaka AI-GBB": {
        "character": "Binaka-half",
        "display_name": "Binaka - AI GBB",
        "avatar": "👩‍💼",
        "customized": True,
        "use_builtin_voice": True,  # Always use built-in voice sync
        "background_image": BACKGROUND_IMAGE_BINAKA_URL
    },
    "Sri AI-GBB": {
        "character": "Sri-half",
        "display_name": "Sri - AI GBB", 
        "avatar": "👨‍💻",
        "customized": True,
        "use_builtin_voice": True,  # Always use built-in voice sync
        "background_image": BACKGROUND_IMAGE_SRI_URL
    },
    "Mike Digital Native": {
        "character": "Mike_Avatar",
        "display_name": "Mike - Digital Native",
        "avatar": "👨‍🎓",
        "customized": True,
        "use_builtin_voice": True,  # Always use built-in voice sync
        "background_image": BACKGROUND_IMAGE_MIKE_URL
    }
}

# Language configurations - Only use voice sync if avatar supports it
LANGUAGE_CONFIG = {
    "English": {
        "code": "en-US",
        "voice": "en-US-JennyNeural",  # Use neural voice as fallback
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
    "Japanese": {
        "code": "ja-JP",
        "voice": "ja-JP-NanamiNeural",
        "flag": "🇯🇵",
        "native_name": "日本語"
    }
}

# Initialize session state
if 'video_history' not in st.session_state:
    st.session_state['video_history'] = []

# Title
st.title("Azure AI Avatar - Microsoft Reference Implementation")
st.write("Using Microsoft's exact reference code for avatar synthesis")

# Check authentication
try:
    auth_header = _authenticate()
    if 'Ocp-Apim-Subscription-Key' in auth_header:
        subscription_key = auth_header['Ocp-Apim-Subscription-Key']
        if subscription_key and subscription_key != 'None':
            st.success(f"✅ Authentication configured (Key: {subscription_key[:8]}...)")
        else:
            st.error("❌ SUBSCRIPTION_KEY or SPEECH_SUBSCRIPTION_KEY not configured")
            st.stop()
    else:
        st.success("✅ Authentication configured (Azure Identity)")
except Exception as e:
    st.error(f"❌ Authentication failed: {str(e)}")
    st.stop()

# Helper functions
def _create_job_id():
    return uuid.uuid4()

def submit_synthesis(job_id: str, text_content: str, avatar_character: str, use_builtin_voice: bool, background_image: str = None):
    """Submit synthesis with useBuiltInVoice set to true"""
    url = f'{SPEECH_ENDPOINT}/avatar/batchsyntheses/{job_id}?api-version={API_VERSION}'
    header = {
        'Content-Type': 'application/json'
    }
    header.update(_authenticate())
    
    isCustomized = True
    
    # Microsoft's exact conditional structure
    if isCustomized:
        avatar_config = {
            "customized": isCustomized,
            "talkingAvatarCharacter": avatar_character,
            "videoFormat": "mp4",
            "videoCodec": "h264",
            "subtitleType": "soft_embedded",
            "backgroundColor": "#FFFFFFFF",
            "useBuiltInVoice": use_builtin_voice  # Set to True for voice sync
        }
    else:
        avatar_config = {
            "customized": isCustomized,
            "talkingAvatarCharacter": avatar_character,
            "talkingAvatarStyle": 'half',
            "videoFormat": "mp4",
            "videoCodec": "h264",
            "subtitleType": "soft_embedded",
            "backgroundColor": "#FFFFFFFF",
            "useBuiltInVoice": use_builtin_voice
        }
    
    # Add background image if provided
    if background_image:
        avatar_config["backgroundImage"] = background_image
    
    # When useBuiltInVoice is True, synthesisConfig should be empty or minimal
    if use_builtin_voice:
        synthesis_config = {}
        st.info("Using built-in voice sync for avatar")
    else:
        synthesis_config = {"voice": "en-US-JennyNeural"}  # Fallback
        st.info("Using neural voice (fallback)")
    
    payload = {
        'synthesisConfig': synthesis_config,
        'customVoices': {},
        "inputKind": "plainText",
        "inputs": [
            {
                "content": text_content.strip(),
            },
        ],
        "avatarConfig": avatar_config
    }
    
    # Display the payload for debugging
    with st.expander("Request Payload", expanded=False):
        st.json(payload)
    
    try:
        response = requests.put(url, json.dumps(payload), headers=header)
        if response.status_code < 400:
            logger.info('Batch avatar synthesis job submitted successfully')
            job_response = response.json()
            logger.info(f'Job ID: {job_response["id"]}')
            return job_response["id"]
        else:
            logger.error(f'Failed to submit batch avatar synthesis job: [{response.status_code}], {response.text}')
            st.error(f'Failed to submit job: {response.status_code} - {response.text}')
            return None
    except Exception as e:
        logger.error(f'Exception during job submission: {str(e)}')
        st.error(f'Exception during job submission: {str(e)}')
        return None

def get_synthesis(job_id):
    """Get synthesis status using Microsoft's exact pattern with detailed error reporting"""
    url = f'{SPEECH_ENDPOINT}/avatar/batchsyntheses/{job_id}?api-version={API_VERSION}'
    header = _authenticate()

    try:
        response = requests.get(url, headers=header)
        if response.status_code < 400:
            logger.debug('Get batch synthesis job successfully')
            response_data = response.json()
            logger.debug(response_data)
            
            if response_data['status'] == 'Succeeded':
                logger.info(f'Batch synthesis job succeeded, download URL: {response_data["outputs"]["result"]}')
                return 'Succeeded', response_data["outputs"]["result"], response_data
            elif response_data['status'] == 'Failed':
                error_info = response_data.get('error', {})
                logger.error(f'Batch synthesis job failed: {error_info}')
                
                # Display detailed error information in Streamlit
                if error_info:
                    st.error(f"**Job Failed with Error:**")
                    st.error(f"**Code:** {error_info.get('code', 'Unknown')}")
                    st.error(f"**Message:** {error_info.get('message', 'No details available')}")
                    if 'details' in error_info:
                        st.error(f"**Details:** {error_info['details']}")
                    
                    # Show full response for debugging
                    with st.expander("Full Error Response", expanded=False):
                        st.json(response_data)
                else:
                    st.error("Job failed but no error details provided")
                    st.json(response_data)
                
                return 'Failed', None, response_data
            else:
                return response_data['status'], None, response_data
        else:
            logger.error(f'Failed to get batch synthesis job: {response.text}')
            st.error(f'Failed to get job status: {response.status_code} - {response.text}')
            return 'Error', None, None
    except Exception as e:
        logger.error(f'Exception during status check: {str(e)}')
        st.error(f'Exception during status check: {str(e)}')
        return 'Error', None, None

# Translation function (simplified)
def get_translation_client():
    if not OPENAI_AVAILABLE or not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME]):
        return None
    try:
        return AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
    except Exception:
        return None

def translate_text(text, target_language, client):
    if not client or target_language == "English":
        return text
    try:
        language_name = LANGUAGE_CONFIG[target_language]["native_name"]
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": f"Translate to {language_name} maintaining professional tone."},
                {"role": "user", "content": text}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return text

# Sidebar
with st.sidebar:
    st.header("Configuration")
    
    # Avatar selection
    selected_avatar_name = st.selectbox(
        "Choose Avatar",
        options=list(CUSTOM_AVATARS.keys()),
        format_func=lambda x: f"{CUSTOM_AVATARS[x]['avatar']} {CUSTOM_AVATARS[x]['display_name']}"
    )
    
    selected_avatar_config = CUSTOM_AVATARS[selected_avatar_name]
    
    # Language selection
    selected_language = st.selectbox(
        "Choose Language",
        options=list(LANGUAGE_CONFIG.keys()),
        format_func=lambda x: f"{LANGUAGE_CONFIG[x]['flag']} {x}"
    )
    
    lang_config = LANGUAGE_CONFIG[selected_language]
    
    st.markdown(f"""
    <div class="language-card">
        <strong>Avatar:</strong> {selected_avatar_config['display_name']}<br>
        <strong>Character:</strong> {selected_avatar_config['character']}<br>
        <strong>Language:</strong> {lang_config['flag']} {selected_language}<br>
        <strong>Voice:</strong> {lang_config['voice']}
    </div>
    """, unsafe_allow_html=True)

# Main content
st.subheader("Input Text")
default_text = "Hi, I'm a virtual assistant created by Microsoft."
input_text = st.text_area("Enter your message:", value=default_text, height=150)

# Translation section
if selected_language != "English":
    st.subheader(f"Translation to {selected_language}")
    translation_client = get_translation_client()
    
    if translation_client:
        if st.button("Translate Text"):
            with st.spinner("Translating..."):
                translated_text = translate_text(input_text, selected_language, translation_client)
                st.session_state['translated_text'] = translated_text
        
        if 'translated_text' in st.session_state:
            st.markdown(f"""
            <div class="translated-text">
                <strong>{lang_config['flag']} Translated Text:</strong><br><br>
                {st.session_state['translated_text']}
            </div>
            """, unsafe_allow_html=True)
            
            edited_translation = st.text_area(
                "Edit translation:",
                value=st.session_state['translated_text'],
                height=100
            )
            if edited_translation != st.session_state['translated_text']:
                st.session_state['translated_text'] = edited_translation
    else:
        st.info("Translation not configured. Using original English text.")

# Generate video button
final_text = input_text
if selected_language != "English" and 'translated_text' in st.session_state:
    final_text = st.session_state['translated_text']

if st.button(f"Generate {selected_language} Avatar Video", type="primary"):
    if not input_text.strip():
        st.warning("Please enter some text.")
    else:
        job_id = _create_job_id()
        
        st.info(f"Submitting job for {selected_avatar_config['display_name']} in {selected_language}...")
        
        # Submit synthesis job
        submitted_job_id = submit_synthesis(
            job_id=job_id,
            text_content=final_text,
            avatar_character=selected_avatar_config['character'],
            use_builtin_voice=selected_avatar_config['use_builtin_voice'],
            background_image=selected_avatar_config.get('background_image')
        )
        
        if submitted_job_id:
            st.success(f"Job submitted successfully! ID: {submitted_job_id}")
            
            # Monitor job status
            progress_bar = st.progress(0)
            status_placeholder = st.empty()
            
            max_attempts = 60
            attempts = 0
            
            while attempts < max_attempts:
                progress = (attempts + 1) / max_attempts
                progress_bar.progress(progress)
                
                status, download_url, response_data = get_synthesis(submitted_job_id)
                
                with status_placeholder.container():
                    st.write(f"**Status:** {status} (Attempt {attempts + 1}/{max_attempts})")
                    if response_data:
                        st.json(response_data)
                
                if status == 'Succeeded' and download_url:
                    st.success("Video generated successfully!")
                    
                    # Store in history
                    video_info = {
                        "name": f"{selected_avatar_config['display_name']}_{selected_language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                        "url": download_url,
                        "language": selected_language,
                        "avatar": selected_avatar_config['display_name'],
                        "timestamp": datetime.now().isoformat()
                    }
                    st.session_state['video_history'].append(video_info)
                    
                    # Display download link and video
                    st.markdown(f"**[Download Video]({download_url})**")
                    st.video(download_url)
                    break
                    
                elif status == 'Failed':
                    st.error("Video generation failed!")
                    if response_data and 'error' in response_data:
                        st.error(f"Error details: {response_data['error']}")
                    break
                    
                else:
                    time.sleep(5)
                
                attempts += 1
            
            if attempts >= max_attempts:
                st.warning("Job monitoring timed out. Check the job status manually.")
        else:
            st.error("Failed to submit synthesis job.")

# Video history
if st.session_state['video_history']:
    st.subheader("Video History")
    for i, video in enumerate(reversed(st.session_state['video_history'])):
        with st.expander(f"{video['language']} - {video['avatar']}: {video['name']}", expanded=False):
            st.write(f"**Created:** {video['timestamp']}")
            st.markdown(f"**[Download]({video['url']})**")
            st.video(video['url'])

# Reset button
if st.button("Reset Session"):
    st.session_state['video_history'] = []
    if 'translated_text' in st.session_state:
        del st.session_state['translated_text']
    st.success("Session reset!")

st.markdown("---")
st.markdown("**Microsoft Azure AI Avatar Reference Implementation**")