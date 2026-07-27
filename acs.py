"""
Azure Communication Services - Voice Call Test (Python Version)
Using only Call Automation API (the Python calling package doesn't exist)

Required packages:
pip install streamlit azure-communication-identity azure-communication-callautomation

"""

import streamlit as st
import time
from datetime import datetime
from azure.communication.identity import CommunicationIdentityClient

# Streamlit page configuration
st.set_page_config(
    page_title="Azure Communication Services Voice Call Test",
    page_icon="📞",
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
    
    .success-card {
        background: #DFF6DD;
        border-left-color: #107C10;
        color: #107C10;
    }
    
    .error-card {
        background: #FFE6E6;
        border-left-color: #FF4444;
        color: #8B0000;
    }
    
    .info-card {
        background: #E6F3FF;
        border-left-color: #0078D4;
        color: #004578;
    }
    
    .warning-card {
        background: #FFF4CE;
        border-left-color: #FF8C00;
        color: #8A6914;
    }
</style>
""", unsafe_allow_html=True)

# Session state initialization
if 'call_logs' not in st.session_state:
    st.session_state.call_logs = []

def log_message(message, status="info"):
    """Add message to call logs"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {
        'timestamp': timestamp,
        'message': message,
        'status': status
    }
    st.session_state.call_logs.append(log_entry)
    if len(st.session_state.call_logs) > 20:
        st.session_state.call_logs.pop(0)

def create_user_token(connection_string: str):
    """
    Create a user and token for potential client-side calling
    Note: This demonstrates token creation only - actual calling requires JavaScript SDK
    """
    try:
        log_message("Creating Communication Identity Client...", "info")
        
        # Create identity client
        identity_client = CommunicationIdentityClient.from_connection_string(connection_string)
        
        log_message("Creating user and token with VoIP scope...", "info")
        
        # Create user and token with VoIP scope
        user = identity_client.create_user()
        token_result = identity_client.get_token(user, ["voip"])
        
        log_message(f"User created: {user.properties['id']}", "info")
        log_message("Token generated successfully", "info")
        
        # Note: The Python SDK for calling is more limited than JavaScript
        # This demonstrates the token creation process
        log_message("Note: Full calling requires JavaScript SDK or Call Automation API", "warning")
        
        return True, f"User and token created successfully. Token expires: {token_result.expires_on}"
        
    except Exception as e:
        error_msg = f"Token creation failed: {str(e)}"
        log_message(error_msg, "error")
        return False, error_msg

def make_call_automation_request(connection_string: str, source_phone: str, target_phone: str, message: str):
    """
    Alternative approach using Call Automation API (server-side calling)
    This is more suitable for Python backend applications
    """
    try:
        log_message("Attempting Call Automation approach...", "info")
        
        # Import Call Automation SDK
        from azure.communication.callautomation import CallAutomationClient
        from azure.communication.callautomation import (
            PhoneNumberIdentifier,
            CallInvite
        )
        
        log_message("Creating Call Automation client...", "info")
        
        # Create call automation client
        call_client = CallAutomationClient.from_connection_string(connection_string)
        
        # Create phone number identifiers
        source_caller = PhoneNumberIdentifier(source_phone)
        target_participant = PhoneNumberIdentifier(target_phone)
        
        # Create call invite
        call_invite = CallInvite(
            target=target_participant,
            source_caller_id_number=source_caller
        )
        
        # For demo purposes, we'll use a placeholder callback URL
        # In production, this would be your actual webhook endpoint
        callback_url = "https://webhook.site/your-webhook-url"  # Replace with actual webhook
        
        log_message(f"Initiating call from {source_phone} to {target_phone}...", "info")
        log_message("Note: Using placeholder callback URL for demo", "warning")
        
        # Create the call with callback URL
        call_connection_properties = call_client.create_call(
            call_invite, 
            callback_url
        )
        call_connection_id = call_connection_properties.call_connection_id
        
        log_message(f"Call initiated! Call ID: {call_connection_id}", "success")
        
        # Get call connection for media operations
        call_connection = call_client.get_call_connection(call_connection_id)
        
        # Wait a moment for call to be established
        time.sleep(3)
        
        # Play message using SSML
        from azure.communication.callautomation import SsmlSource
        
        ssml_text = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
            <voice name="en-US-AriaNeural">
                <prosody rate="medium" pitch="medium">
                    {message}
                </prosody>
            </voice>
        </speak>
        """
        
        play_source = SsmlSource(ssml_text=ssml_text)
        
        log_message("Playing message to recipient...", "info")
        
        # Play the message
        result = call_connection.play_media_to_all(play_source=play_source)
        
        log_message("Message played successfully", "success")
        
        # Wait for message to complete
        time.sleep(10)
        
        # Hang up
        call_connection.hang_up(is_for_everyone=True)
        log_message("Call completed and hung up", "success")
        
        return True, "Voice call completed successfully"
        
    except ImportError:
        error_msg = "Call Automation SDK not installed. Run: pip install azure-communication-callautomation"
        log_message(error_msg, "error")
        return False, error_msg
    except Exception as e:
        error_msg = f"Call automation failed: {str(e)}"
        log_message(error_msg, "error")
        return False, error_msg

def main():
    """Main Streamlit application"""
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📞 Azure Communication Services Voice Call Test</h1>
        <p>Python implementation for making voice calls with text-to-speech</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Important note about Python vs JavaScript
    st.markdown("""
    <div class="status-card warning-card">
        <strong>⚠️ Important Note:</strong> The Azure Communication Services Calling SDK works differently in Python vs JavaScript.<br>
        • <strong>JavaScript SDK:</strong> Full client-side calling features<br>
        • <strong>Python SDK:</strong> Server-side call automation (better for your use case)<br>
        • This app uses Call Automation API which is ideal for automated notifications
    </div>
    """, unsafe_allow_html=True)
    
    # Configuration section
    st.subheader("Configuration")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Connection details
        connection_string = st.text_input(
            "Azure Communication Services Connection String",
            type="password",
            help="Your regenerated connection string from Azure portal"
        )
        
        # Phone numbers
        st.markdown("**Phone Numbers**")
        col_source, col_target = st.columns(2)
        
        with col_source:
            source_phone = st.text_input(
                "Source Phone (Azure Number)",
                value="+18332475723",
                help="Your Azure Communication Services phone number"
            )
        
        with col_target:
            target_phone = st.text_input(
                "Target Phone (Your Phone)",
                value="+15109538089",
                help="Your personal phone number (with country code)"
            )
        
        # Message content
        message = st.text_area(
            "Voice Message",
            value="Hello! This is an automated call from your Azure Communication Services customer support system. Case number 12345 has been resolved by our AI agents. The customer issue has been successfully processed and documented. Thank you.",
            height=100,
            help="Text that will be converted to speech during the call"
        )
    
    with col2:
        # Status and info
        st.markdown("""
        <div class="status-card info-card">
            <strong>📋 Call Information</strong><br>
            • Uses Azure Call Automation API<br>
            • Text-to-speech with neural voices<br>
            • Automatic call management<br>
            • Perfect for notifications
        </div>
        """, unsafe_allow_html=True)
        
        # Quick test messages
        st.markdown("**Quick Test Messages**")
        if st.button("🚨 Emergency Alert", use_container_width=True):
            st.session_state.quick_message = "URGENT: Critical customer support case requires immediate attention. Case number 99999. High priority escalation needed."
        
        if st.button("✅ Case Resolved", use_container_width=True):
            st.session_state.quick_message = "Customer support notification: Case number 12345 has been successfully resolved by our AI agent system. All issues have been addressed."
        
        if st.button("📋 Status Update", use_container_width=True):
            st.session_state.quick_message = "Case status update: Your customer support request is being processed by our AI agents. We will notify you when complete."
        
        # Set quick message if selected
        if 'quick_message' in st.session_state:
            message = st.session_state.quick_message
            del st.session_state.quick_message
            st.rerun()
    
    # Action buttons
    st.subheader("Actions")
    
    col_call, col_token, col_clear = st.columns([2, 2, 1])
    
    with col_call:
        if st.button("📞 Make Voice Call", type="primary", use_container_width=True):
            if not connection_string:
                st.error("Please enter your connection string")
            elif not target_phone.startswith('+'):
                st.error("Target phone must include country code (e.g., +15109538089)")
            else:
                with st.spinner("Making voice call..."):
                    success, result = make_call_automation_request(
                        connection_string, 
                        source_phone, 
                        target_phone, 
                        message
                    )
                    
                    if success:
                        st.success(result)
                    else:
                        st.error(result)
    
    with col_token:
        if st.button("🔑 Test Token Creation", use_container_width=True):
            if not connection_string:
                st.error("Please enter your connection string")
            else:
                with st.spinner("Creating user and token..."):
                    success, result = create_user_token(connection_string)
                    
                    if success:
                        st.success(result)
                    else:
                        st.error(result)
    
    with col_clear:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.call_logs = []
            st.rerun()
    
    # Call logs
    if st.session_state.call_logs:
        st.subheader("Call Logs")
        
        for log in reversed(st.session_state.call_logs[-10:]):
            if log['status'] == 'success':
                card_class = 'success-card'
            elif log['status'] == 'error':
                card_class = 'error-card'
            elif log['status'] == 'warning':
                card_class = 'warning-card'
            else:
                card_class = 'status-card'
            
            st.markdown(f"""
            <div class="status-card {card_class}">
                <strong>[{log['timestamp']}]</strong> {log['message']}
            </div>
            """, unsafe_allow_html=True)
    
    # Installation instructions
    st.subheader("Setup Instructions")
    st.info("""
    1. **Install required packages:**
       ```
       pip install azure-communication-callautomation azure-communication-identity
       ```
    
    2. **Use your regenerated connection string** (after the security incident)
    
    3. **Verify phone number format** includes country code (+15109538089)
    
    4. **Test the call** - your phone should ring and play the message
    """)
    
    # Integration guidance
    with st.expander("💡 Integration with Customer Support System"):
        st.markdown("""
        **Integration approach for your multi-agent system:**
        
        ```python
        # In your customer support workflow
        def notify_case_completion(case_data, resolution_summary):
            # Create notification message
            message = f"Case {case_data['Case Number']} resolved. "
            message += f"Customer: {case_data['Customer Name']}. "
            message += f"Issue: {case_data['Issue Description'][:50]}. "
            message += "Resolution completed by AI agents."
            
            # Make notification call
            make_call_automation_request(
                connection_string=AZURE_CONNECTION_STRING,
                source_phone="+18332475723",
                target_phone=MANAGER_PHONE,
                message=message
            )
        ```
        
        **Notification Strategy:**
        - **Critical cases:** Immediate voice call
        - **Standard cases:** SMS notification
        - **Bulk updates:** Daily summary call
        - **System errors:** Immediate call to technical team
        
        This Call Automation approach is perfect for server-side notifications
        and integrates well with your existing multi-agent customer support system.
        """)

if __name__ == "__main__":
    main()