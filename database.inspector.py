import streamlit as st
import json
import os
import time
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING, ASCENDING
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict

# Load environment variables
load_dotenv(override=True)

# Security password
SECURITY_PASSWORD = "ai-gbb-2026"

# Azure Cosmos DB MongoDB configuration
COSMOS_CONNECTION_STRING = os.getenv("AZCOSMOS_CONNSTR")
COSMOS_DATABASE_NAME = os.getenv("AZCOSMOS_DATABASE_NAME_Batch", "avatarbatch")
COSMOS_CONTAINER_NAME = os.getenv("AZCOSMOS_CONTAINER_NAME_batch", "avatarbatch")

# Set up the page configuration
st.set_page_config(
    page_title="Azure Avatar Database Inspector",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# Initialize MongoDB connection
@st.cache_resource
def init_mongo_connection():
    """Initialize MongoDB connection with caching"""
    try:
        if not COSMOS_CONNECTION_STRING:
            st.error("❌ COSMOS_CONNECTION_STRING not configured")
            return None, None
        
        client = MongoClient(COSMOS_CONNECTION_STRING)
        db = client[COSMOS_DATABASE_NAME]
        collection = db[COSMOS_CONTAINER_NAME]
        
        # Test connection
        client.server_info()
        return client, collection
    except Exception as e:
        st.error(f"❌ Failed to connect to MongoDB: {str(e)}")
        return None, None

# Password protection
if not st.session_state['authenticated']:
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h1>🔐 Database Inspector - Secure Access</h1>
        <p style="font-size: 18px; color: #666;">Please enter the security password to access the Database Inspector</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("Enter Password:", type="password", placeholder="Security password required")
        
        if st.button("🚀 Access Database Inspector", type="primary"):
            if password == SECURITY_PASSWORD:
                st.session_state['authenticated'] = True
                st.success("✅ Access granted! Redirecting...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Incorrect password. Please try again.")
    
    st.markdown("""
    <div style="text-align: center; margin-top: 50px; color: #888;">
        <p>🤖 Azure Avatar Database Inspector | Secure Data Management Tool</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.stop()

# Custom CSS
st.markdown("""
    <style>
    .stApp {
        background-color: #E5F8FF;
        background-image: linear-gradient(to right, #B2FFEC, #D9F4FF);
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        text-align: center;
        border-left: 5px solid #0078D4;
    }
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
        color: #0078D4;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 1em;
        color: #666;
        font-weight: 500;
    }
    .data-card {
        background: white;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #ff6b35;
    }
    .status-badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: bold;
    }
    .status-success {
        background-color: #d4edda;
        color: #155724;
    }
    .status-info {
        background-color: #d1ecf1;
        color: #0c5460;
    }
    .status-warning {
        background-color: #fff3cd;
        color: #856404;
    }
    h1 {
        color: #0078D4;
    }
    h2 {
        color: #106EBE;
    }
    </style>
""", unsafe_allow_html=True)

# Add logout button
col1, col2 = st.columns([9, 1])
with col2:
    if st.button("🔓 Logout", key="logout_btn"):
        st.session_state['authenticated'] = False
        st.rerun()

# Initialize database connection
mongo_client, mongo_collection = init_mongo_connection()

if mongo_collection is None:
    st.error("❌ Cannot proceed without database connection. Please check your configuration.")
    st.stop()

# Main header
st.title("🔍 Azure Avatar Database Inspector")
st.markdown("**Comprehensive Database Monitoring & Analytics Dashboard**")
st.markdown("---")

# Sidebar navigation
st.sidebar.title("📊 Navigation")
page = st.sidebar.radio(
    "Select View",
    [
        "📈 Overview Dashboard",
        "👥 User Analytics",
        "🎭 Avatar Analytics",
        "🌍 Language Analytics",
        "📋 Raw Data Explorer",
        "🔄 Recent Activity",
        "🗑️ Data Management"
    ]
)

# Helper functions
def get_database_stats():
    """Get comprehensive database statistics"""
    try:
        total_docs = mongo_collection.count_documents({})
        
        # Get unique users
        unique_users = mongo_collection.distinct("username")
        
        # Get avatar distribution
        avatar_pipeline = [
            {"$group": {"_id": "$avatar_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        avatar_dist = list(mongo_collection.aggregate(avatar_pipeline))
        
        # Get language distribution
        language_pipeline = [
            {"$group": {"_id": "$language", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        language_dist = list(mongo_collection.aggregate(language_pipeline))
        
        # Get total tokens
        token_pipeline = [
            {"$group": {"_id": None, "total_tokens": {"$sum": "$tokens"}}}
        ]
        token_result = list(mongo_collection.aggregate(token_pipeline))
        total_tokens = token_result[0]['total_tokens'] if token_result else 0
        
        # Get customer distribution
        customer_pipeline = [
            {"$group": {"_id": "$customer_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        customer_dist = list(mongo_collection.aggregate(customer_pipeline))
        
        # Get date range
        first_doc = mongo_collection.find_one(sort=[("timestamp", ASCENDING)])
        last_doc = mongo_collection.find_one(sort=[("timestamp", DESCENDING)])
        
        return {
            "total_engagements": total_docs,
            "unique_users": len(unique_users),
            "avatar_distribution": avatar_dist,
            "language_distribution": language_dist,
            "total_tokens": total_tokens,
            "customer_distribution": customer_dist,
            "first_engagement": first_doc.get('timestamp') if first_doc else None,
            "last_engagement": last_doc.get('timestamp') if last_doc else None,
            "user_list": unique_users
        }
    except Exception as e:
        st.error(f"Error getting database stats: {str(e)}")
        return None

def get_user_details(username):
    """Get detailed statistics for a specific user"""
    try:
        user_docs = list(mongo_collection.find({"username": username}).sort("timestamp", DESCENDING))
        
        if not user_docs:
            return None
        
        total_tokens = sum(doc.get('tokens', 0) for doc in user_docs)
        
        # Avatar breakdown
        avatar_breakdown = defaultdict(int)
        for doc in user_docs:
            avatar_breakdown[doc.get('avatar_name', 'Unknown')] += 1
        
        # Language breakdown
        language_breakdown = defaultdict(int)
        for doc in user_docs:
            language_breakdown[doc.get('language', 'Unknown')] += 1
        
        # Customer breakdown
        customer_breakdown = defaultdict(int)
        for doc in user_docs:
            customer_breakdown[doc.get('customer_name', 'Unknown')] += 1
        
        return {
            "total_engagements": len(user_docs),
            "total_tokens": total_tokens,
            "avatar_breakdown": dict(avatar_breakdown),
            "language_breakdown": dict(language_breakdown),
            "customer_breakdown": dict(customer_breakdown),
            "recent_activities": user_docs[:10]
        }
    except Exception as e:
        st.error(f"Error getting user details: {str(e)}")
        return None

def get_avatar_stats():
    """Get comprehensive avatar statistics"""
    try:
        # Get all avatars with their stats
        avatar_pipeline = [
            {
                "$group": {
                    "_id": "$avatar_name",
                    "total_videos": {"$sum": 1},
                    "total_tokens": {"$sum": "$tokens"},
                    "unique_users": {"$addToSet": "$username"},
                    "languages": {"$addToSet": "$language"}
                }
            },
            {"$sort": {"total_videos": -1}}
        ]
        avatar_stats = list(mongo_collection.aggregate(avatar_pipeline))
        
        # Process results
        for stat in avatar_stats:
            stat['unique_users_count'] = len(stat['unique_users'])
            stat['languages_count'] = len(stat['languages'])
            stat['avg_tokens'] = stat['total_tokens'] / stat['total_videos'] if stat['total_videos'] > 0 else 0
        
        return avatar_stats
    except Exception as e:
        st.error(f"Error getting avatar stats: {str(e)}")
        return []

def get_language_stats():
    """Get comprehensive language statistics"""
    try:
        language_pipeline = [
            {
                "$group": {
                    "_id": "$language",
                    "total_videos": {"$sum": 1},
                    "total_tokens": {"$sum": "$tokens"},
                    "unique_users": {"$addToSet": "$username"},
                    "avatars": {"$addToSet": "$avatar_name"}
                }
            },
            {"$sort": {"total_videos": -1}}
        ]
        language_stats = list(mongo_collection.aggregate(language_pipeline))
        
        # Process results
        for stat in language_stats:
            stat['unique_users_count'] = len(stat['unique_users'])
            stat['avatars_count'] = len(stat['avatars'])
            stat['avg_tokens'] = stat['total_tokens'] / stat['total_videos'] if stat['total_videos'] > 0 else 0
        
        return language_stats
    except Exception as e:
        st.error(f"Error getting language stats: {str(e)}")
        return []

def get_recent_activity(limit=50):
    """Get recent database activity"""
    try:
        recent = list(mongo_collection.find().sort("timestamp", DESCENDING).limit(limit))
        return recent
    except Exception as e:
        st.error(f"Error getting recent activity: {str(e)}")
        return []

# PAGE ROUTING
if page == "📈 Overview Dashboard":
    st.header("📈 Overview Dashboard")
    
    with st.spinner("Loading database statistics..."):
        stats = get_database_stats()
    
    if stats:
        # Top metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Engagements</div>
                <div class="metric-value">{stats['total_engagements']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Unique Users</div>
                <div class="metric-value">{stats['unique_users']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Tokens</div>
                <div class="metric-value">{stats['total_tokens']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            avg_tokens = stats['total_tokens'] / max(1, stats['total_engagements'])
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Avg Tokens/Video</div>
                <div class="metric-value">{avg_tokens:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Date range
        col1, col2 = st.columns(2)
        with col1:
            if stats['first_engagement']:
                st.info(f"**First Engagement:** {stats['first_engagement']}")
        with col2:
            if stats['last_engagement']:
                st.info(f"**Last Engagement:** {stats['last_engagement']}")
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎭 Avatar Distribution")
            if stats['avatar_distribution']:
                avatar_df = pd.DataFrame(stats['avatar_distribution'])
                fig = px.pie(
                    avatar_df,
                    values='count',
                    names='_id',
                    title='Videos by Avatar',
                    color_discrete_sequence=px.colors.sequential.Blues_r
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("🌍 Language Distribution")
            if stats['language_distribution']:
                lang_df = pd.DataFrame(stats['language_distribution'])
                fig = px.bar(
                    lang_df,
                    x='_id',
                    y='count',
                    title='Videos by Language',
                    labels={'_id': 'Language', 'count': 'Video Count'},
                    color='count',
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Top customers
        st.subheader("👔 Top 10 Customers")
        if stats['customer_distribution']:
            customer_df = pd.DataFrame(stats['customer_distribution'])
            customer_df.columns = ['Customer', 'Videos']
            st.dataframe(customer_df, use_container_width=True, hide_index=True)

elif page == "👥 User Analytics":
    st.header("👥 User Analytics")
    
    stats = get_database_stats()
    
    if stats and stats['user_list']:
        st.success(f"**Total Users in Database:** {len(stats['user_list'])}")
        
        # User selector
        selected_user = st.selectbox(
            "Select User to Analyze",
            options=sorted(stats['user_list']),
            index=0
        )
        
        if selected_user:
            with st.spinner(f"Loading data for {selected_user}..."):
                user_details = get_user_details(selected_user)
            
            if user_details:
                st.markdown("---")
                
                # User metrics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">Total Videos</div>
                        <div class="metric-value">{user_details['total_engagements']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">Total Tokens</div>
                        <div class="metric-value">{user_details['total_tokens']:,}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    avg = user_details['total_tokens'] / max(1, user_details['total_engagements'])
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">Avg Tokens</div>
                        <div class="metric-value">{avg:.1f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Breakdown charts
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🎭 Avatar Usage")
                    if user_details['avatar_breakdown']:
                        avatar_df = pd.DataFrame(
                            list(user_details['avatar_breakdown'].items()),
                            columns=['Avatar', 'Count']
                        )
                        fig = px.bar(
                            avatar_df,
                            x='Avatar',
                            y='Count',
                            color='Count',
                            color_continuous_scale='Blues'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("🌍 Language Usage")
                    if user_details['language_breakdown']:
                        lang_df = pd.DataFrame(
                            list(user_details['language_breakdown'].items()),
                            columns=['Language', 'Count']
                        )
                        fig = px.pie(
                            lang_df,
                            values='Count',
                            names='Language',
                            color_discrete_sequence=px.colors.sequential.RdBu
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                
                # Customer breakdown
                st.subheader("👔 Customer Engagements")
                if user_details['customer_breakdown']:
                    customer_df = pd.DataFrame(
                        list(user_details['customer_breakdown'].items()),
                        columns=['Customer', 'Videos']
                    ).sort_values('Videos', ascending=False)
                    st.dataframe(customer_df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Recent activities
                st.subheader("📋 Recent Activities (Last 10)")
                for i, activity in enumerate(user_details['recent_activities'], 1):
                    with st.expander(f"#{i} - {activity.get('avatar_name')} | {activity.get('language')} | {activity.get('timestamp', 'N/A')}"):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write(f"**Customer:** {activity.get('customer_name', 'N/A')}")
                            st.write(f"**Avatar:** {activity.get('avatar_name', 'N/A')}")
                            st.write(f"**Language:** {activity.get('language', 'N/A')}")
                            st.write(f"**Tokens:** {activity.get('tokens', 0)}")
                            st.write(f"**Timestamp:** {activity.get('timestamp', 'N/A')}")
                        
                        with col2:
                            if activity.get('video_url'):
                                st.markdown(f"[🎥 Video Link]({activity['video_url']})")
                            st.write(f"**ID:** `{activity.get('_id', 'N/A')}`")
                        
                        if activity.get('input_text'):
                            st.text_area("Input Text", activity['input_text'], height=100, disabled=True)
            else:
                st.warning(f"No data found for user: {selected_user}")
    else:
        st.info("No users found in database.")

elif page == "🎭 Avatar Analytics":
    st.header("🎭 Avatar Analytics")
    
    with st.spinner("Loading avatar statistics..."):
        avatar_stats = get_avatar_stats()
    
    if avatar_stats:
        st.success(f"**Total Avatars Used:** {len(avatar_stats)}")
        
        # Overview metrics
        for avatar in avatar_stats:
            with st.expander(f"🎭 {avatar['_id']}", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Videos", f"{avatar['total_videos']:,}")
                
                with col2:
                    st.metric("Total Tokens", f"{avatar['total_tokens']:,}")
                
                with col3:
                    st.metric("Unique Users", f"{avatar['unique_users_count']:,}")
                
                with col4:
                    st.metric("Avg Tokens", f"{avatar['avg_tokens']:.1f}")
                
                st.markdown("---")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Languages Used:**")
                    for lang in avatar['languages']:
                        st.markdown(f"- {lang}")
                
                with col2:
                    st.write("**Top Users:**")
                    for user in list(avatar['unique_users'])[:5]:
                        st.markdown(f"- {user}")
    else:
        st.info("No avatar statistics available.")

elif page == "🌍 Language Analytics":
    st.header("🌍 Language Analytics")
    
    with st.spinner("Loading language statistics..."):
        language_stats = get_language_stats()
    
    if language_stats:
        st.success(f"**Total Languages Used:** {len(language_stats)}")
        
        # Overview metrics
        for lang in language_stats:
            with st.expander(f"🌍 {lang['_id']}", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Videos", f"{lang['total_videos']:,}")
                
                with col2:
                    st.metric("Total Tokens", f"{lang['total_tokens']:,}")
                
                with col3:
                    st.metric("Unique Users", f"{lang['unique_users_count']:,}")
                
                with col4:
                    st.metric("Avg Tokens", f"{lang['avg_tokens']:.1f}")
                
                st.markdown("---")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Avatars Used:**")
                    for avatar in lang['avatars']:
                        st.markdown(f"- {avatar}")
                
                with col2:
                    st.write("**Top Users:**")
                    for user in list(lang['unique_users'])[:5]:
                        st.markdown(f"- {user}")
    else:
        st.info("No language statistics available.")

elif page == "📋 Raw Data Explorer":
    st.header("📋 Raw Data Explorer")
    
    # Query options
    st.subheader("Query Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        query_type = st.selectbox(
            "Query Type",
            ["All Documents", "By Username", "By Avatar", "By Language", "By Customer", "Custom Query"]
        )
    
    with col2:
        limit = st.number_input("Limit Results", min_value=1, max_value=1000, value=50)
    
    # Build query based on selection
    query = {}
    
    if query_type == "By Username":
        stats = get_database_stats()
        if stats and stats['user_list']:
            username = st.selectbox("Select Username", sorted(stats['user_list']))
            query = {"username": username}
    
    elif query_type == "By Avatar":
        avatar = st.selectbox("Select Avatar", ["Binaka-AI GBB Leader", "Sri-AI GBB Leader", "Mike-AI GBB Leader"])
        query = {"avatar_name": avatar}
    
    elif query_type == "By Language":
        language = st.selectbox("Select Language", ["English", "Spanish", "French", "German", "Hindi", "Japanese", "Portuguese", "Chinese"])
        query = {"language": language}
    
    elif query_type == "By Customer":
        customer = st.text_input("Enter Customer Name")
        if customer:
            query = {"customer_name": customer}
    
    elif query_type == "Custom Query":
        query_json = st.text_area("Enter MongoDB Query (JSON)", value='{}', height=100)
        try:
            query = json.loads(query_json)
        except:
            st.error("Invalid JSON query")
            query = {}
    
    # Execute query
    if st.button("🔍 Execute Query", type="primary"):
        with st.spinner("Executing query..."):
            try:
                results = list(mongo_collection.find(query).sort("timestamp", DESCENDING).limit(limit))
                
                st.success(f"Found {len(results)} documents")
                
                if results:
                    # Convert to DataFrame for display
                    df = pd.DataFrame(results)
                    
                    # Select columns to display
                    display_cols = st.multiselect(
                        "Select Columns to Display",
                        options=list(df.columns),
                        default=['timestamp', 'username', 'customer_name', 'avatar_name', 'language', 'tokens']
                    )
                    
                    if display_cols:
                        st.dataframe(df[display_cols], use_container_width=True)
                    
                    # Export option
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download as CSV",
                        data=csv,
                        file_name=f"avatar_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    # Show individual documents
                    st.markdown("---")
                    st.subheader("Individual Documents")
                    
                    for i, doc in enumerate(results, 1):
                        with st.expander(f"Document #{i} - {doc.get('timestamp', 'N/A')}"):
                            st.json(doc, expanded=False)
                else:
                    st.info("No documents found matching the query.")
            
            except Exception as e:
                st.error(f"Error executing query: {str(e)}")

elif page == "🔄 Recent Activity":
    st.header("🔄 Recent Activity")
    
    refresh = st.button("🔄 Refresh", type="primary")
    
    limit = st.slider("Number of recent activities to show", min_value=10, max_value=200, value=50, step=10)
    
    with st.spinner(f"Loading last {limit} activities..."):
        recent = get_recent_activity(limit)
    
    if recent:
        st.success(f"Showing {len(recent)} most recent activities")
        
        for i, activity in enumerate(recent, 1):
            timestamp = activity.get('timestamp', 'N/A')
            username = activity.get('username', 'N/A')
            customer = activity.get('customer_name', 'N/A')
            avatar = activity.get('avatar_name', 'N/A')
            language = activity.get('language', 'N/A')
            tokens = activity.get('tokens', 0)
            
            with st.expander(f"#{i} - {username} | {avatar} | {language} | {timestamp}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"""
                    <div class="data-card">
                        <strong>Username:</strong> {username}<br>
                        <strong>Customer:</strong> {customer}<br>
                        <strong>Avatar:</strong> {avatar}<br>
                        <strong>Language:</strong> {language}<br>
                        <strong>Tokens:</strong> {tokens}<br>
                        <strong>Timestamp:</strong> {timestamp}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    if activity.get('video_url'):
                        st.markdown(f"[🎥 Video Link]({activity['video_url']})")
                    st.code(str(activity.get('_id', 'N/A')), language='text')
                
                if activity.get('input_text'):
                    st.text_area("Input Text", activity['input_text'], height=100, disabled=True, key=f"text_{i}")
    else:
        st.info("No recent activity found.")

elif page == "🗑️ Data Management":
    st.header("🗑️ Data Management")
    
    st.warning("⚠️ **Warning:** These operations will modify the database. Use with caution!")
    
    # Delete operations
    st.subheader("Delete Operations")
    
    delete_type = st.selectbox(
        "Select Delete Operation",
        ["Delete by Username", "Delete by Customer", "Delete by Date Range", "Delete All (Danger!)"]
    )
    
    if delete_type == "Delete by Username":
        stats = get_database_stats()
        if stats and stats['user_list']:
            username = st.selectbox("Select Username to Delete", sorted(stats['user_list']))
            
            # Show preview
            count = mongo_collection.count_documents({"username": username})
            st.info(f"This will delete {count} documents for user: {username}")
            
            confirm = st.text_input("Type 'DELETE' to confirm")
            
            if st.button("🗑️ Delete User Data", type="primary"):
                if confirm == "DELETE":
                    result = mongo_collection.delete_many({"username": username})
                    st.success(f"✅ Deleted {result.deleted_count} documents for {username}")
                else:
                    st.error("Confirmation text doesn't match. Operation cancelled.")
    
    elif delete_type == "Delete by Customer":
        customer_name = st.text_input("Enter Customer Name")
        
        if customer_name:
            count = mongo_collection.count_documents({"customer_name": customer_name})
            st.info(f"This will delete {count} documents for customer: {customer_name}")
            
            confirm = st.text_input("Type 'DELETE' to confirm")
            
            if st.button("🗑️ Delete Customer Data", type="primary"):
                if confirm == "DELETE":
                    result = mongo_collection.delete_many({"customer_name": customer_name})
                    st.success(f"✅ Deleted {result.deleted_count} documents for {customer_name}")
                else:
                    st.error("Confirmation text doesn't match. Operation cancelled.")
    
    elif delete_type == "Delete by Date Range":
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input("Start Date")
        
        with col2:
            end_date = st.date_input("End Date")
        
        if start_date and end_date:
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
            
            query = {
                "timestamp": {
                    "$gte": start_str,
                    "$lt": end_str
                }
            }
            
            count = mongo_collection.count_documents(query)
            st.info(f"This will delete {count} documents between {start_date} and {end_date}")
            
            confirm = st.text_input("Type 'DELETE' to confirm")
            
            if st.button("🗑️ Delete Date Range", type="primary"):
                if confirm == "DELETE":
                    result = mongo_collection.delete_many(query)
                    st.success(f"✅ Deleted {result.deleted_count} documents")
                else:
                    st.error("Confirmation text doesn't match. Operation cancelled.")
    
    elif delete_type == "Delete All (Danger!)":
        st.error("🚨 **DANGER ZONE** 🚨")
        st.error("This will delete ALL documents in the database!")
        
        total = mongo_collection.count_documents({})
        st.error(f"This will delete {total} total documents!")
        
        confirm1 = st.text_input("Type 'DELETE ALL' to confirm")
        confirm2 = st.text_input("Type the total number of documents to confirm", type="password")
        
        if st.button("🗑️ DELETE ALL DATA", type="primary"):
            if confirm1 == "DELETE ALL" and confirm2 == str(total):
                result = mongo_collection.delete_many({})
                st.success(f"✅ Deleted {result.deleted_count} documents")
                st.balloons()
            else:
                st.error("Confirmation failed. Operation cancelled.")
    
    st.markdown("---")
    
    # Export operations
    st.subheader("📤 Export Operations")
    
    export_type = st.selectbox(
        "Select Export Type",
        ["Export All Data", "Export by Username", "Export by Date Range"]
    )
    
    if st.button("📥 Export to JSON", type="primary"):
        try:
            query = {}
            
            if export_type == "Export by Username":
                stats = get_database_stats()
                if stats and stats['user_list']:
                    username = st.selectbox("Select Username", sorted(stats['user_list']), key="export_user")
                    query = {"username": username}
            
            elif export_type == "Export by Date Range":
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Start Date", key="export_start")
                with col2:
                    end_date = st.date_input("End Date", key="export_end")
                
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                
                query = {
                    "timestamp": {
                        "$gte": start_str,
                        "$lt": end_str
                    }
                }
            
            data = list(mongo_collection.find(query))
            
            # Convert ObjectId to string for JSON serialization
            for doc in data:
                doc['_id'] = str(doc['_id'])
            
            json_str = json.dumps(data, indent=2, default=str)
            
            st.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name=f"avatar_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
            
            st.success(f"✅ Exported {len(data)} documents")
        
        except Exception as e:
            st.error(f"Export failed: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>🔍 Azure Avatar Database Inspector | Powered by Azure Cosmos DB & Streamlit</p>
    <p><strong>Contact:</strong> <a href="mailto:ganac@microsoft.com" style="color: #0078D4; text-decoration: none;">ganac@microsoft.com</a> (AI-GBB Team)</p>
</div>
""", unsafe_allow_html=True)