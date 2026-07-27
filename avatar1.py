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

# Load environment variables
load_dotenv(override=True)

# Accessing environment variables
SPEECH_ENDPOINT = os.getenv("SPEECH_ENDPOINT")
SUBSCRIPTION_KEY = os.getenv("SPEECH_SUBSCRIPTION_KEY")
BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")
API_VERSION = os.getenv("API_VERSION", "2024-04-15-preview")
BACKGROUND_IMAGE_URL = os.getenv("BACKGROUND_IMAGE_URL")

# Set up the page configuration
st.set_page_config(page_title="Azure AI Text-to-Speech Avatar", layout="wide")

# Custom CSS to apply background color and styles
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
    .voice-card {
        background: white;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #0078D4;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Adjust the headline
st.title("Elevate Your Sales Pitch: Create Personalized AI-Driven Videos with the Help of AI Avatar, Your AI GBB Agent")
st.write("Create and download videos using your custom avatars and neural voices.")

# Input fields on the left side
with st.sidebar:
    st.header("User Information")
    username = st.text_input("Username", value="")
    industry_vertical = st.selectbox("Industry Vertical", ["education", "healthcare", "manufacturing", "telecom", "sdp", "finance", "other"])
    customer_name = st.text_input("Customer Name", value="")
    date = st.date_input("Date", value=datetime.now().date())
    
    st.markdown("---")
    
    # Voice selection - only working voices
    st.header("Voice Settings")
    voice_options = [
        'en-US-AvaMultilingualNeural',
        'en-US-JennyNeural'
    ]
    
    voice_descriptions = [
        'Ava - Multilingual Neural (Recommended)',
        'Jenny - Natural Female Voice'
    ]
    
    selected_voice_index = st.selectbox(
        "Choose Avatar Voice", 
        options=range(len(voice_options)),
        format_func=lambda x: voice_descriptions[x]
    )
    
    # Avatar character selection
    st.header("Avatar Settings")
    avatar_character = st.selectbox(
        "Choose Avatar Character",
        options=["lisa"],
        format_func=lambda x: f"{x.title()} - Professional Avatar"
    )
    
    avatar_style = st.selectbox(
        "Choose Avatar Style",
        options=["graceful-sitting", "casual-sitting"],
        format_func=lambda x: x.replace("-", " ").title()
    )

if username and industry_vertical and customer_name:
    default_input_text = (
        f"Welcome {customer_name}! I'm AI-Avatar, your AI partner from the Global Black Belt AI Team at Microsoft. "
        "We're thrilled that you've chosen to explore AI solutions with us. Our team is eager to collaborate with you to build cutting-edge AI solutions using Microsoft Azure AI services, along with our trusted partners. "
        "Let's embark on this journey together and transform your business with the power of AI. This personalized avatar is here to assist you and provide all the information you need."
    )
else:
    default_input_text = "Hi, I'm AI-Avatar, your AI partner from the Global Black Belt AI Team at Microsoft."

# Input field for Text to Speech
st.subheader("Input Text (Text to Speech)")
input_text = st.text_area("Input Text", value=default_input_text, height=150)

# Character count and validation
char_count = len(input_text)
max_chars = 3000
st.caption(f"Characters: {char_count}/{max_chars}")

if char_count > max_chars:
    st.error(f"Text is too long. Please reduce by {char_count - max_chars} characters.")

# Blob storage initialization
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

def _create_job_id():
    return str(uuid.uuid4())

def _authenticate(subscription_key):
    return {'Ocp-Apim-Subscription-Key': subscription_key}

def check_existing_files(username, industry_vertical, customer_name, file_type):
    if not blob_connected:
        return 1
    file_prefix = f"{username}_{industry_vertical}_{customer_name}_AI-Avatar_{file_type}"
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

def submit_synthesis(job_id: str, input_text: str, selected_voice: str, avatar_char: str, avatar_style_setting: str):
    """Submit synthesis job"""
    endpoint = SPEECH_ENDPOINT.rstrip('/')
    url = f'{endpoint}/avatar/batchsyntheses/{job_id}?api-version={API_VERSION}'
    
    header = {
        'Content-Type': 'application/json',
        'Ocp-Apim-Subscription-Key': SUBSCRIPTION_KEY
    }

    payload = {
        'synthesisConfig': {
            "voice": selected_voice,
            "outputFormat": "riff-24khz-16bit-mono-pcm"
        },
        "inputKind": "plainText",
        "inputs": [{"content": input_text.strip()}],
        "avatarConfig": {
            "customized": False,
            "talkingAvatarCharacter": avatar_char,
            "talkingAvatarStyle": avatar_style_setting,
            "videoFormat": "mp4",
            "videoCodec": "h264",
            "subtitleType": "soft_embedded",
            "backgroundColor": "#FFFFFF"
        }
    }
    
    # Only add background image if it's provided and not OneDrive
    if BACKGROUND_IMAGE_URL and BACKGROUND_IMAGE_URL.strip():
        if "1drv.ms" not in BACKGROUND_IMAGE_URL.lower() and "onedrive" not in BACKGROUND_IMAGE_URL.lower():
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

def generate_filename(username, industry_vertical, customer_name, count, extension, file_type):
    return f"{username}_{industry_vertical}_{customer_name}_AI-Avatar_{file_type}{count}.{extension}"

def generate_srt(subtitle_data):
    """Generate SRT file content"""
    srt_content = ""
    for idx, entry in enumerate(subtitle_data):
        start_time = format_srt_time(entry['start_time'])
        end_time = format_srt_time(entry['end_time'])
        srt_content += f"{idx+1}\n"
        srt_content += f"{start_time} --> {end_time}\n"
        srt_content += f"{entry['text']}\n\n"
    return srt_content

def save_srt_file(srt_content, srt_filename):
    try:
        with open(srt_filename, 'w', encoding='utf-8') as srt_file:
            srt_file.write(srt_content)
        return srt_filename
    except Exception:
        return None

def format_srt_time(milliseconds):
    """Convert milliseconds to SRT time format"""
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{int(ms):03}"

def extract_word_timestamps(response_data):
    """Extract word-level timestamps"""
    word_timestamps = []
    word_boundary = response_data.get('wordBoundary', [])
    for word_info in word_boundary:
        word_timestamps.append({
            'start_time': word_info.get('start', 0),
            'end_time': word_info.get('end', 0),
            'text': word_info.get('word', '')
        })
    return word_timestamps

# Validation
if not SPEECH_ENDPOINT or not SUBSCRIPTION_KEY:
    st.error("Please configure SPEECH_ENDPOINT and SPEECH_SUBSCRIPTION_KEY in your .env file")
    st.stop()

# Display selected settings
with st.expander("Current Settings", expanded=False):
    st.write(f"**Voice:** {voice_descriptions[selected_voice_index]}")
    st.write(f"**Avatar:** {avatar_character.title()} - {avatar_style.replace('-', ' ').title()}")
    st.write(f"**Text Length:** {char_count} characters")

# Submit button
if st.button("Submit for Synthesis", type="primary", disabled=(char_count > max_chars)):
    if not username or not input_text or not customer_name:
        st.warning("Please enter username, text, and customer name.")
    elif char_count > max_chars:
        st.error(f"Text is too long. Maximum {max_chars} characters allowed.")
    else:
        job_id = _create_job_id()
        recording_count = check_existing_files(username, industry_vertical, customer_name, "recordings")
        selected_voice = voice_options[selected_voice_index]
        
        # Submit synthesis job
        submitted_job_id = submit_synthesis(job_id, input_text, selected_voice, avatar_character, avatar_style)
        if submitted_job_id:
            st.info(f"Job submitted successfully. ID: {submitted_job_id}")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            with st.spinner("Processing avatar video..."):
                max_attempts = 60
                attempts = 0
                video_content = None
                
                while attempts < max_attempts:
                    progress = (attempts + 1) / max_attempts
                    progress_bar.progress(progress)
                    status_text.text(f"Processing... {attempts + 1}/{max_attempts}")
                    
                    download_url, response_data = get_synthesis(submitted_job_id)
                    
                    if download_url and response_data:
                        st.success("Video generated successfully!")
                        progress_bar.progress(1.0)
                        status_text.text("Completed!")

                        video_name = generate_filename(username, industry_vertical, customer_name, recording_count, "mp4", "recordings")
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

                            # Generate subtitles
                            subtitle_data = extract_word_timestamps(response_data)
                            if subtitle_data:
                                srt_content = generate_srt(subtitle_data)
                                srt_filename = f"{video_name}.srt"
                                if save_srt_file(srt_content, srt_filename):
                                    st.info("Subtitles generated")

                            # Upload to blob storage
                            blob_url = upload_to_blob(local_video_path, video_name)
                            sas_token = generate_sas_token(video_name) if blob_connected else ""
                            
                            st.session_state['video_history'].append({
                                "name": video_name,
                                "url": blob_url,
                                "sas_token": sas_token,
                                "timestamp": datetime.now().isoformat()
                            })

                            # Display results
                            col1, col2 = st.columns([1, 1])
                            
                            with col1:
                                if video_content:
                                    st.download_button(
                                        label="Download Video",
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

# Feedback section
st.subheader("Feedback")
feedback = st.text_area("Please provide feedback if you have any suggestions for improvement.")

if feedback and st.button("Submit Feedback"):
    if blob_connected:
        try:
            feedback_count = check_existing_files(username, industry_vertical, customer_name, "feedback")
            feedback_filename = generate_filename(username, industry_vertical, customer_name, feedback_count, "txt", "feedback")
            feedback_blob_client = container_client.get_blob_client(feedback_filename)
            feedback_blob_client.upload_blob(feedback)
            st.success("Thank you for your feedback!")
        except Exception:
            st.error("Failed to save feedback")
    else:
        st.warning("Feedback cannot be saved - storage not configured")

# Video history
st.subheader("Session Video History")
if st.session_state['video_history']:
    for i, video in enumerate(reversed(st.session_state['video_history'])):
        with st.expander(f"Video {len(st.session_state['video_history']) - i}: {video['name']}", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
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
    st.session_state['video_history'] = []
    st.success("Session reset successfully.")

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>Powered by Azure AI Services | Microsoft Global Black Belt AI Team</p>
</div>
""", unsafe_allow_html=True)