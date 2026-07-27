import streamlit as st
import json
import logging
import os
import sys
import time
import uuid
import requests
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone
import base64
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv(override=True)

# Accessing environment variables
SPEECH_ENDPOINT = os.getenv("SPEECH_ENDPOINT")
SUBSCRIPTION_KEY = os.getenv("SPEECH_SUBSCRIPTION_KEY")
BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")
API_VERSION = os.getenv("API_VERSION", "2024-04-15-preview")
BACKGROUND_IMAGE_URL = os.getenv("BACKGROUND_IMAGE_URL")

# Azure OpenAI for translation
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Set up the page configuration
st.set_page_config(page_title="Multilingual Azure AI Avatar", layout="wide")

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

# Language configurations
LANGUAGE_CONFIG = {
    "English": {
        "code": "en-US",
        "voice": "en-US-AvaMultilingualNeural",
        "avatar_character": "lisa",
        "flag": "🇺🇸",
        "native_name": "English"
    },
    "Spanish": {
        "code": "es-ES",
        "voice": "es-ES-ElviraNeural",
        "avatar_character": "lisa",
        "flag": "🇪🇸",
        "native_name": "Español"
    },
    "French": {
        "code": "fr-FR",
        "voice": "fr-FR-DeniseNeural", 
        "avatar_character": "lisa",
        "flag": "🇫🇷",
        "native_name": "Français"
    },
    "German": {
        "code": "de-DE",
        "voice": "de-DE-KatjaNeural",
        "avatar_character": "lisa",
        "flag": "🇩🇪",
        "native_name": "Deutsch"
    },
    "Japanese": {
        "code": "ja-JP",
        "voice": "ja-JP-NanamiNeural",
        "avatar_character": "lisa",
        "flag": "🇯🇵",
        "native_name": "日本語"
    }
}

# Initialize Azure OpenAI client for translation
def get_translation_client():
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT_NAME:
        return AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
    return None

def translate_text(text, target_language, client):
    """Translate text using Azure OpenAI"""
    if not client or target_language == "English":
        return text
    
    try:
        language_name = LANGUAGE_CONFIG[target_language]["native_name"]
        
        prompt = f"""Translate the following English text to {language_name}. 
        Maintain a professional, friendly tone suitable for business communication.
        Keep the same meaning and context.
        
        Text to translate:
        {text}
        
        Translated text:"""
        
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate English text to {language_name} while maintaining the business context and friendly tone."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        translated_text = response.choices[0].message.content.strip()
        # Remove "Translated text:" prefix if present
        if translated_text.startswith("Translated text:"):
            translated_text = translated_text.replace("Translated text:", "").strip()
        
        return translated_text
    except Exception as e:
        st.error(f"Translation failed: {str(e)}")
        return text

# Title
st.title("Elevate Your Sales Pitch: Create Personalized AI-Driven Videos with the Help of AI Avatar, Your AI GBB Agent")
st.write("Create and download videos using your custom avatars and neural voices.")

# Sidebar
with st.sidebar:
    st.header("User Information")
    username = st.text_input("Username", value="")
    industry_vertical = st.selectbox("Industry Vertical", ["education", "healthcare", "manufacturing", "telecom", "sdp", "finance", "other"])
    customer_name = st.text_input("Customer Name", value="")
    date = st.date_input("Date", value=datetime.now().date())
    
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
    
    # Avatar style
    st.header("Avatar Settings")
    avatar_style = st.selectbox(
        "Choose Avatar Style",
        options=["graceful-sitting", "casual-sitting"],
        format_func=lambda x: x.replace("-", " ").title()
    )

# Default text generation
if username and industry_vertical and customer_name:
    default_input_text = (
        f"Welcome {customer_name}! I'm AI-Avatar, your AI partner from the Global Black Belt AI Team at Microsoft. "
        "We're thrilled that you've chosen to explore AI solutions with us. Our team is eager to collaborate with you to build cutting-edge AI solutions using Microsoft Azure AI services, along with our trusted partners. "
        "Let's embark on this journey together and transform your business with the power of AI. This personalized avatar is here to assist you and provide all the information you need."
    )
else:
    default_input_text = "Hi, I'm AI-Avatar, your AI partner from the Global Black Belt AI Team at Microsoft."

# Input text
st.subheader("Input Text (English)")
input_text = st.text_area("Enter your message in English:", value=default_input_text, height=150)

# Character count
char_count = len(input_text)
max_chars = 3000
st.caption(f"Characters: {char_count}/{max_chars}")

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
                st.session_state['translated_text'] = translated_text
        
        # Display translated text
        if 'translated_text' in st.session_state:
            st.markdown(f"""
            <div class="translated-text">
                <strong>{LANGUAGE_CONFIG[selected_language]['flag']} Translated Text ({selected_language}):</strong><br><br>
                {st.session_state['translated_text']}
            </div>
            """, unsafe_allow_html=True)
            
            # Option to edit translated text
            edited_translation = st.text_area(
                f"Edit translation if needed:",
                value=st.session_state['translated_text'],
                height=100
            )
            if edited_translation != st.session_state['translated_text']:
                st.session_state['translated_text'] = edited_translation
    else:
        st.warning("Translation service not configured. Please set Azure OpenAI environment variables.")
        st.info("The avatar will use the original English text.")

# Blob storage setup
if BLOB_CONNECTION_STRING:
    try:
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        container_client.get_container_properties()
        blob_connected = True
    except Exception:
        blob_connected = False
else:
    blob_connected = False

if 'video_history' not in st.session_state:
    st.session_state['video_history'] = []

# Helper functions (same as before)
def _create_job_id():
    return str(uuid.uuid4())

def _authenticate(subscription_key):
    return {'Ocp-Apim-Subscription-Key': subscription_key}

def check_existing_files(username, industry_vertical, customer_name, file_type, language):
    if not blob_connected:
        return 1
    file_prefix = f"{username}_{industry_vertical}_{customer_name}_{language}_Maria_{file_type}"
    try:
        existing_files = container_client.list_blobs(name_starts_with=file_prefix)
        count = 1
        for blob in existing_files:
            blob_name = blob.name
            parts = blob_name.split("_")
            if len(parts) >= 4 and parts[-1].startswith(file_type):
                number_part = parts[-1].replace(file_type, "").replace(".mp4", "").replace(".webm", "").replace(".txt", "")
                try:
                    number = int(number_part)
                    if number >= count:
                        count = number + 1
                except ValueError:
                    continue
        return count
    except Exception:
        return 1

def generate_sas_token(blob_name):
    if not blob_connected:
        return ""
    try:
        sas_token = generate_blob_sas(
            account_name=blob_service_client.account_name,
            container_name=BLOB_CONTAINER_NAME,
            blob_name=blob_name,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        return sas_token
    except Exception:
        return ""

def submit_synthesis(job_id: str, text_content: str, language_config: dict, avatar_style_setting: str):
    """Submit synthesis job with language-specific settings"""
    endpoint = SPEECH_ENDPOINT.rstrip('/')
    url = f'{endpoint}/avatar/batchsyntheses/{job_id}?api-version={API_VERSION}'
    
    header = {
        'Content-Type': 'application/json',
        'Ocp-Apim-Subscription-Key': SUBSCRIPTION_KEY
    }

    payload = {
        'synthesisConfig': {
            "voice": language_config['voice'],
            "outputFormat": "riff-24khz-16bit-mono-pcm"
        },
        "inputKind": "plainText",
        "inputs": [{"content": text_content.strip()}],
        "avatarConfig": {
            "customized": False,
            "talkingAvatarCharacter": language_config['avatar_character'],
            "talkingAvatarStyle": avatar_style_setting,
            "videoFormat": "mp4",
            "videoCodec": "h264",
            "subtitleType": "soft_embedded",
            "backgroundColor": "#FFFFFF"
        }
    }
    
    # Add background image if provided
    if BACKGROUND_IMAGE_URL and BACKGROUND_IMAGE_URL.strip():
        payload["avatarConfig"]["backgroundImage"] = BACKGROUND_IMAGE_URL

    try:
        response = requests.put(url, json=payload, headers=header, timeout=30)
        
        if response.status_code < 400:
            response_json = response.json()
            return response_json.get("id")
        else:
            st.error(f'Failed to submit synthesis job. Status: {response.status_code}')
            return None
            
    except Exception as e:
        st.error(f'Request failed: {str(e)}')
        return None

def get_synthesis(job_id):
    """Check synthesis job status"""
    endpoint = SPEECH_ENDPOINT.rstrip('/')
    url = f'{endpoint}/avatar/batchsyntheses/{job_id}?api-version={API_VERSION}'
    header = _authenticate(SUBSCRIPTION_KEY)

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

def upload_to_blob(local_filename, blob_name):
    if not blob_connected:
        return "local://" + local_filename
    try:
        blob_client = container_client.get_blob_client(blob_name)
        with open(local_filename, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        return blob_client.url
    except Exception as e:
        st.error(f"Failed to upload to blob storage: {str(e)}")
        return None

def generate_filename(username, industry_vertical, customer_name, language, count, extension, file_type):
    return f"{username}_{industry_vertical}_{customer_name}_{language}_Maria_{file_type}{count}.{extension}"

# Validation
if not SPEECH_ENDPOINT or not SUBSCRIPTION_KEY:
    st.error("Please configure SPEECH_ENDPOINT and SPEECH_SUBSCRIPTION_KEY in your .env file")
    st.stop()

# Display current settings
with st.expander("Current Settings", expanded=False):
    st.write(f"**Language:** {selected_language} {lang_config['flag']}")
    st.write(f"**Voice:** {lang_config['voice']}")
    st.write(f"**Avatar Style:** {avatar_style.replace('-', ' ').title()}")
    st.write(f"**Text Length:** {char_count} characters")

# Submit button
final_text = input_text
if selected_language != "English" and 'translated_text' in st.session_state:
    final_text = st.session_state['translated_text']

if st.button(f"Generate {selected_language} Avatar Video", type="primary", disabled=(char_count > max_chars)):
    if not username or not input_text or not customer_name:
        st.warning("Please enter username, text, and customer name.")
    elif char_count > max_chars:
        st.error(f"Text is too long. Maximum {max_chars} characters allowed.")
    elif selected_language != "English" and 'translated_text' not in st.session_state:
        st.warning("Please translate the text first before generating the video.")
    else:
        job_id = _create_job_id()
        recording_count = check_existing_files(username, industry_vertical, customer_name, "recordings", selected_language)
        
        st.info(f"Creating {selected_language} avatar video with {lang_config['voice']} voice...")
        
        # Submit synthesis job
        submitted_job_id = submit_synthesis(job_id, final_text, lang_config, avatar_style)
        if submitted_job_id:
            st.info(f"Job submitted successfully. ID: {submitted_job_id}")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            with st.spinner(f"Processing {selected_language} avatar video..."):
                max_attempts = 60
                attempts = 0
                video_content = None
                
                while attempts < max_attempts:
                    progress = (attempts + 1) / max_attempts
                    progress_bar.progress(progress)
                    status_text.text(f"Processing... {attempts + 1}/{max_attempts}")
                    
                    download_url, response_data = get_synthesis(submitted_job_id)
                    
                    if download_url and response_data:
                        st.success(f"{selected_language} video generated successfully!")
                        progress_bar.progress(1.0)
                        status_text.text("Completed!")

                        video_name = generate_filename(username, industry_vertical, customer_name, selected_language, recording_count, "mp4", "recordings")
                        local_video_path = video_name

                        # Download video
                        try:
                            with requests.get(download_url, stream=True) as r:
                                r.raise_for_status()
                                video_content = b''
                                with open(local_video_path, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                        video_content += chunk

                            # Upload to blob storage
                            blob_url = upload_to_blob(local_video_path, video_name)
                            sas_token = generate_sas_token(video_name) if blob_connected else ""
                            
                            st.session_state['video_history'].append({
                                "name": video_name,
                                "url": blob_url,
                                "sas_token": sas_token,
                                "language": selected_language,
                                "flag": lang_config['flag'],
                                "timestamp": datetime.now().isoformat()
                            })

                            # Display results
                            col1, col2 = st.columns([1, 1])
                            
                            with col1:
                                if video_content:
                                    st.download_button(
                                        label=f"Download {selected_language} Video",
                                        data=video_content,
                                        file_name=video_name,
                                        mime='video/mp4',
                                        type="primary"
                                    )
                            
                            with col2:
                                if blob_url and sas_token:
                                    video_url_with_sas = f"{blob_url}?{sas_token}"
                                    st.video(video_url_with_sas)
                                elif blob_url:
                                    st.video(blob_url)
                            
                            # Clean up
                            try:
                                os.remove(local_video_path)
                            except:
                                pass
                            
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

# Video history
st.subheader("Multilingual Video History")
if st.session_state['video_history']:
    for i, video in enumerate(reversed(st.session_state['video_history'])):
        with st.expander(f"{video['flag']} {video['language']} Video {len(st.session_state['video_history']) - i}: {video['name']}", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Language:** {video['flag']} {video['language']}")
                st.write(f"**Created:** {video.get('timestamp', 'Unknown')}")
                if video.get('sas_token'):
                    video_sas_url = f"{video['url']}?{video['sas_token']}"
                    st.markdown(f"[Download Link]({video_sas_url})")
                else:
                    st.write(f"**URL:** {video['url']}")
            
            with col2:
                if video.get('sas_token'):
                    video_sas_url = f"{video['url']}?{video['sas_token']}"
                    st.video(video_sas_url)
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
    <p>Powered by Azure AI Services | Multilingual Avatar Technology</p>
</div>
""", unsafe_allow_html=True)