"""
Azure Voice Live Streamlit Application - Simplified Stable Version

This creates a simpler integration that avoids session state issues
by keeping the Microsoft reference code mostly unchanged.

Required Environment Variables (.env file):
AZURE_VOICE_LIVE_API_KEY=your_api_key_here
AZURE_VOICE_LIVE_ENDPOINT=your_endpoint_here

Required packages:
pip install streamlit azure-ai-voicelive pyaudio python-dotenv azure-core azure-identity
"""

import streamlit as st
import os
import sys
import asyncio
import base64
import threading
import queue
import time
import logging
from datetime import datetime
from typing import Union, Optional, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor

# Environment variable loading
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    st.warning("python-dotenv not installed. Using existing environment variables.")

# Audio processing imports
try:
    import pyaudio
except ImportError:
    st.error("This app requires pyaudio. Install with: pip install pyaudio")
    st.stop()

# Azure VoiceLive SDK imports
try:
    from azure.core.credentials import AzureKeyCredential, TokenCredential
    from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
    from azure.ai.voicelive.aio import connect
    
    if TYPE_CHECKING:
        from azure.ai.voicelive.aio import VoiceLiveConnection
    
    from azure.ai.voicelive.models import (
        RequestSession,
        ServerVad,
        AzureStandardVoice,
        Modality,
        AudioFormat,
        ServerEventType,
    )
except ImportError as e:
    st.error(f"Missing Azure Voice Live SDK: {e}")
    st.error("Install with: pip install azure-ai-voicelive")
    st.stop()

# Streamlit configuration
st.set_page_config(
    page_title="Azure Voice Live Assistant",
    page_icon="🎤",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #F3F2F1;
    }
    
    .main-header {
        background: linear-gradient(90deg, #0078D4 0%, #106EBE 100%);
        color: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    
    .status-card {
        background: white;
        padding: 15px;
        border-radius: 6px;
        border-left: 4px solid #0078D4;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    .status-ready { border-left-color: #107C10; background: #DFF6DD; }
    .status-connecting { border-left-color: #FF8C00; background: #FFF4CE; }
    .status-listening { border-left-color: #0078D4; background: #E6F3FF; }
    .status-processing { border-left-color: #FF8C00; background: #FFF4CE; }
    .status-responding { border-left-color: #5C2D91; background: #F3E5F5; }
    .status-error { border-left-color: #FF4444; background: #FFE6E6; }
    .status-stopped { border-left-color: #666666; background: #F5F5F5; }
</style>
""", unsafe_allow_html=True)

# Simple session state initialization
if 'voice_status' not in st.session_state:
    st.session_state.voice_status = 'stopped'
if 'is_running' not in st.session_state:
    st.session_state.is_running = False

# Global status for thread communication (thread-safe)
class VoiceStatus:
    def __init__(self):
        self.status = 'stopped'
        self.message = 'Voice assistant stopped'
        self.logs = []
    
    def update_status(self, status, message):
        self.status = status
        self.message = message
        self.add_log(f"Status: {status} - {message}")
    
    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        if len(self.logs) > 50:
            self.logs.pop(0)
        # Also print to console
        print(log_entry)

# Global status object
voice_status = VoiceStatus()

class AudioProcessor:
    """
    Microsoft reference implementation - minimal changes
    """

    def __init__(self, connection):
        self.connection = connection
        self.audio = pyaudio.PyAudio()

        # Audio configuration - PCM16, 24kHz, mono as specified
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 24000
        self.chunk_size = 1024

        # Capture and playback state
        self.is_capturing = False
        self.is_playing = False
        self.input_stream = None
        self.output_stream = None

        # Audio queues and threading
        self.audio_queue: "queue.Queue[bytes]" = queue.Queue()
        self.audio_send_queue: "queue.Queue[str]" = queue.Queue()  # base64 audio to send
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.capture_thread: Optional[threading.Thread] = None
        self.playback_thread: Optional[threading.Thread] = None
        self.send_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None  # Store the event loop

        voice_status.add_log("AudioProcessor initialized with 24kHz PCM16 mono audio")

    async def start_capture(self):
        """Start capturing audio from microphone."""
        if self.is_capturing:
            return

        # Store the current event loop for use in threads
        self.loop = asyncio.get_event_loop()

        self.is_capturing = True

        try:
            self.input_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=None,
            )

            self.input_stream.start_stream()

            # Start capture thread
            self.capture_thread = threading.Thread(target=self._capture_audio_thread)
            self.capture_thread.daemon = True
            self.capture_thread.start()

            # Start audio send thread
            self.send_thread = threading.Thread(target=self._send_audio_thread)
            self.send_thread.daemon = True
            self.send_thread.start()

            voice_status.add_log("Started audio capture")

        except Exception as e:
            voice_status.add_log(f"Failed to start audio capture: {e}")
            self.is_capturing = False
            raise

    def _capture_audio_thread(self):
        """Audio capture thread - runs in background."""
        while self.is_capturing and self.input_stream:
            try:
                # Read audio data
                audio_data = self.input_stream.read(self.chunk_size, exception_on_overflow=False)

                if audio_data and self.is_capturing:
                    # Convert to base64 and queue for sending
                    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                    self.audio_send_queue.put(audio_base64)

            except Exception as e:
                if self.is_capturing:
                    voice_status.add_log(f"Error in audio capture: {e}")
                break

    def _send_audio_thread(self):
        """Audio send thread - handles async operations from sync thread."""
        while self.is_capturing:
            try:
                # Get audio data from queue (blocking with timeout)
                audio_base64 = self.audio_send_queue.get(timeout=0.1)

                if audio_base64 and self.is_capturing and self.loop:
                    # Schedule the async send operation in the main event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.connection.input_audio_buffer.append(audio=audio_base64), self.loop
                    )
                    # Don't wait for completion to avoid blocking

            except queue.Empty:
                continue
            except Exception as e:
                if self.is_capturing:
                    voice_status.add_log(f"Error sending audio: {e}")
                break

    async def stop_capture(self):
        """Stop capturing audio."""
        if not self.is_capturing:
            return

        self.is_capturing = False

        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None

        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)

        if self.send_thread:
            self.send_thread.join(timeout=1.0)

        # Clear the send queue
        while not self.audio_send_queue.empty():
            try:
                self.audio_send_queue.get_nowait()
            except queue.Empty:
                break

        voice_status.add_log("Stopped audio capture")

    async def start_playback(self):
        """Initialize audio playback system."""
        if self.is_playing:
            return

        self.is_playing = True

        try:
            self.output_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk_size,
            )

            # Start playback thread
            self.playback_thread = threading.Thread(target=self._playback_audio_thread)
            self.playback_thread.daemon = True
            self.playback_thread.start()

            voice_status.add_log("Audio playback system ready")

        except Exception as e:
            voice_status.add_log(f"Failed to initialize audio playback: {e}")
            self.is_playing = False
            raise

    def _playback_audio_thread(self):
        """Audio playback thread - runs in background."""
        while self.is_playing:
            try:
                # Get audio data from queue (blocking with timeout)
                audio_data = self.audio_queue.get(timeout=0.1)

                if audio_data and self.output_stream and self.is_playing:
                    self.output_stream.write(audio_data)

            except queue.Empty:
                continue
            except Exception as e:
                if self.is_playing:
                    voice_status.add_log(f"Error in audio playback: {e}")
                break

    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback."""
        if self.is_playing:
            self.audio_queue.put(audio_data)

    async def stop_playback(self):
        """Stop audio playback and clear queue."""
        if not self.is_playing:
            return

        self.is_playing = False

        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None

        if self.playback_thread:
            self.playback_thread.join(timeout=1.0)

        voice_status.add_log("Stopped audio playback")

    async def cleanup(self):
        """Clean up audio resources."""
        await self.stop_capture()
        await self.stop_playback()

        if self.audio:
            self.audio.terminate()

        self.executor.shutdown(wait=True)
        voice_status.add_log("Audio processor cleaned up")

class BasicVoiceAssistant:
    """
    Microsoft reference implementation - minimal changes
    """

    def __init__(
        self,
        endpoint: str,
        credential: Union[AzureKeyCredential, TokenCredential],
        model: str,
        voice: str,
        instructions: str,
    ):

        self.endpoint = endpoint
        self.credential = credential
        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.connection: Optional["VoiceLiveConnection"] = None
        self.audio_processor: Optional[AudioProcessor] = None
        self.session_ready = False
        self.conversation_started = False

    async def start(self):
        """Start the voice assistant session."""
        try:
            voice_status.update_status('connecting', f'Connecting to VoiceLive API with model {self.model}')

            # Connect to VoiceLive WebSocket API
            async with connect(
                endpoint=self.endpoint,
                credential=self.credential,
                model=self.model,
                connection_options={
                    "max_msg_size": 10 * 1024 * 1024,
                    "heartbeat": 20,
                    "timeout": 20,
                },
            ) as connection:
                conn = connection
                self.connection = conn

                # Initialize audio processor
                ap = AudioProcessor(conn)
                self.audio_processor = ap

                # Configure session for voice conversation
                await self._setup_session()

                # Start audio systems
                await ap.start_playback()

                voice_status.update_status('ready', 'Voice assistant ready! Start speaking...')

                # Process events
                await self._process_events()

        except KeyboardInterrupt:
            voice_status.update_status('stopped', 'Voice assistant interrupted')

        except Exception as e:
            voice_status.update_status('error', f'Connection error: {e}')
            raise

        # Cleanup
        if self.audio_processor:
            await self.audio_processor.cleanup()

        voice_status.update_status('stopped', 'Voice assistant stopped')

    async def _setup_session(self):
        """Configure the VoiceLive session for audio conversation."""
        voice_status.add_log("Setting up voice conversation session...")

        # Create strongly typed voice configuration
        voice_config: Union[AzureStandardVoice, str]
        if self.voice.startswith("en-US-") or self.voice.startswith("en-CA-") or "-" in self.voice:
            # Azure voice
            voice_config = AzureStandardVoice(name=self.voice, type="azure-standard")
        else:
            # OpenAI voice (alloy, echo, fable, onyx, nova, shimmer)
            voice_config = self.voice

        # Create strongly typed turn detection configuration
        turn_detection_config = ServerVad(threshold=0.5, prefix_padding_ms=300, silence_duration_ms=500)

        # Create strongly typed session configuration
        session_config = RequestSession(
            modalities=[Modality.TEXT, Modality.AUDIO],
            instructions=self.instructions,
            voice=voice_config,
            input_audio_format=AudioFormat.PCM16,
            output_audio_format=AudioFormat.PCM16,
            turn_detection=turn_detection_config,
        )

        conn = self.connection
        assert conn is not None, "Connection must be established before setting up session"
        await conn.session.update(session=session_config)

        voice_status.add_log("Session configuration sent")

    async def _process_events(self):
        """Process events from the VoiceLive connection."""
        try:
            conn = self.connection
            assert conn is not None, "Connection must be established before processing events"
            async for event in conn:
                await self._handle_event(event)

        except KeyboardInterrupt:
            voice_status.add_log("Event processing interrupted")
        except Exception as e:
            voice_status.add_log(f"Error processing events: {e}")
            raise

    async def _handle_event(self, event):
        """Handle different types of events from VoiceLive."""
        voice_status.add_log(f"Received event: {event.type}")
        ap = self.audio_processor
        conn = self.connection
        assert ap is not None, "AudioProcessor must be initialized"
        assert conn is not None, "Connection must be established"

        if event.type == ServerEventType.SESSION_UPDATED:
            voice_status.add_log(f"Session ready: {event.session.id}")
            self.session_ready = True

            # Start audio capture once session is ready
            await ap.start_capture()

        elif event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
            voice_status.update_status('listening', 'User started speaking - listening...')

            # Stop current assistant audio playback (interruption handling)
            await ap.stop_playback()

            # Cancel any ongoing response
            try:
                await conn.response.cancel()
            except Exception as e:
                voice_status.add_log(f"No response to cancel: {e}")

        elif event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
            voice_status.update_status('processing', 'User stopped speaking - processing...')

            # Restart playback system for response
            await ap.start_playback()

        elif event.type == ServerEventType.RESPONSE_CREATED:
            voice_status.update_status('responding', 'Assistant response created')

        elif event.type == ServerEventType.RESPONSE_AUDIO_DELTA:
            # Stream audio response to speakers
            await ap.queue_audio(event.delta)

        elif event.type == ServerEventType.RESPONSE_AUDIO_DONE:
            voice_status.update_status('ready', 'Assistant finished speaking - ready for next input')

        elif event.type == ServerEventType.RESPONSE_DONE:
            voice_status.add_log("Response complete")

        elif event.type == ServerEventType.ERROR:
            voice_status.update_status('error', f'VoiceLive error: {event.error.message}')

        elif event.type == ServerEventType.CONVERSATION_ITEM_CREATED:
            voice_status.add_log(f"Conversation item created: {event.item.id}")

        else:
            voice_status.add_log(f"Unhandled event type: {event.type}")

def run_voice_assistant_thread(endpoint: str, api_key: str, model: str, voice: str, instructions: str):
    """Run the voice assistant in a background thread."""
    
    def assistant_thread():
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create credential
            credential = AzureKeyCredential(api_key)
            
            # Create and start voice assistant
            assistant = BasicVoiceAssistant(
                endpoint=endpoint,
                credential=credential,
                model=model,
                voice=voice,
                instructions=instructions,
            )
            
            # Start the assistant
            loop.run_until_complete(assistant.start())
            
        except KeyboardInterrupt:
            voice_status.update_status('stopped', 'Voice assistant interrupted by user')
        except Exception as e:
            voice_status.update_status('error', f'Assistant error: {str(e)}')
        finally:
            try:
                loop.close()
            except:
                pass
            st.session_state.is_running = False
    
    # Start the assistant thread
    st.session_state.is_running = True
    thread = threading.Thread(target=assistant_thread, name="VoiceAssistant")
    thread.daemon = True
    thread.start()

def main():
    """Main Streamlit application"""
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🎤 Azure Voice Live Assistant</h1>
        <p>Stable Microsoft Reference Implementation</p>
    </div>
    """, unsafe_allow_html=True)

    # Configuration section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Configuration")
        
        api_key = st.text_input(
            "Azure Voice Live API Key",
            value=os.getenv("AZURE_VOICE_LIVE_API_KEY", ""),
            type="password",
            help="Enter your Azure Voice Live API key"
        )
        
        endpoint = st.text_input(
            "Endpoint",
            value=os.getenv("AZURE_VOICE_LIVE_ENDPOINT", ""),
            help="Azure Voice Live WebSocket endpoint URL"
        )
        
        col_model, col_voice = st.columns(2)
        
        with col_model:
            model = st.selectbox(
                "Model",
                ["gpt-4o-realtime-preview", "gpt-4o-mini-realtime-preview"],
                index=0
            )
        
        with col_voice:
            voice = st.selectbox(
                "Voice",
                ["en-US-AvaNeural", "en-US-GuyNeural", "alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                index=0
            )
        
        instructions = st.text_area(
            "Instructions",
            value=os.getenv(
                "VOICE_LIVE_INSTRUCTIONS",
                "You are a helpful AI assistant. Respond naturally and conversationally. Keep your responses concise but engaging."
            ),
            height=100
        )

    with col2:
        # Status display - get from global status
        status = voice_status.status
        message = voice_status.message
        
        status_icons = {
            'stopped': '⚪',
            'connecting': '🟡',
            'ready': '🟢',
            'listening': '🎤',
            'processing': '🤔',
            'responding': '🗣️',
            'error': '🔴'
        }
        
        icon = status_icons.get(status, '⚪')
        
        st.markdown(f"""
        <div class="status-card status-{status}">
            <strong>{icon} Status</strong><br>
            {message}
        </div>
        """, unsafe_allow_html=True)
    
    # Control buttons
    st.subheader("Controls")
    
    col_start, col_stop, col_clear = st.columns(3)
    
    with col_start:
        if st.button("🎤 Start Voice Assistant", type="primary", disabled=st.session_state.is_running):
            if not api_key:
                st.error("Please enter your API key")
            elif not endpoint:
                st.error("Please enter the endpoint URL")
            else:
                # Clear logs for new session
                voice_status.logs = []
                run_voice_assistant_thread(endpoint, api_key, model, voice, instructions)
                time.sleep(0.5)
                st.rerun()
    
    with col_stop:
        if st.button("⏹️ Stop", disabled=not st.session_state.is_running):
            st.session_state.is_running = False
            voice_status.update_status('stopped', 'Stopping voice assistant...')
            st.rerun()
    
    with col_clear:
        if st.button("🗑️ Clear Log"):
            voice_status.logs = []
            st.rerun()

    # Auto-refresh while running
    if st.session_state.is_running:
        time.sleep(1)
        st.rerun()

    # Console output
    if voice_status.logs:
        st.subheader("Console Output")
        # Show last 20 log entries
        recent_logs = voice_status.logs[-20:]
        for log in recent_logs:
            st.text(log)

    # Instructions
    st.subheader("Instructions")
    st.info("""
    1. Enter your Azure Voice Live API key and endpoint above
    2. Click "Start Voice Assistant" 
    3. Wait for status to show "ready"
    4. Start speaking when you see the microphone icon
    5. The assistant will respond with voice
    
    **This uses the Microsoft reference implementation with minimal changes** 
    for maximum stability and compatibility.
    """)

if __name__ == "__main__":
    main()