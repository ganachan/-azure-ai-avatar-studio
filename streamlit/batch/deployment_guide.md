# AI Avatar Global Analytics System
## Comprehensive Deployment Guide and Configuration

### Overview
This system provides global analytics and metrics tracking for your AI Avatar applications across Streamlit, HTML, and API interfaces. It uses Azure Cosmos DB (MongoDB API) to store engagement data and provide real-time analytics.

### Key Features
- ✅ **Global Metrics Tracking**: Track videos generated, users, tokens consumed across all applications
- ✅ **User-Specific Analytics**: Individual user statistics, engagement streaks, favorite avatars
- ✅ **Industry Insights**: Analytics breakdown by industry verticals
- ✅ **Real-time Dashboard**: Comprehensive analytics dashboard with charts and trends
- ✅ **Multi-Application Support**: Works with Streamlit, HTML, and API interfaces
- ✅ **Persistent Data**: All metrics persist across sessions and application restarts
- ✅ **AI Recommendations**: Generate intelligent business recommendations based on conversation history

### Architecture Components

#### 1. Core Analytics System (`global_avatar_analytics.py`)
- **GlobalAvatarAnalytics**: Main analytics class
- **UserEngagement**: Data model for engagement tracking
- **GlobalMetrics**: Platform-wide metrics aggregation
- **Database Collections**:
  - `user_engagements`: Individual engagement records
  - `global_metrics`: Aggregated platform metrics
  - `user_profiles`: User-specific data and statistics

#### 2. Enhanced Streamlit App (`enhanced_streamlit_app.py`)
- Multi-page application with analytics integration
- Global metrics display
- User profile management
- Enhanced video generation with analytics tracking
- Real-time metrics updates

#### 3. Enhanced HTML App (`enhanced_html_avatar_app.html`)
- Industry-focused interface with analytics
- Real-time global metrics display
- AI-powered recommendations
- Conversation history tracking
- Integrated analytics API calls

#### 4. Backend API (`analytics_api.py`)
- RESTful API for analytics operations
- FastAPI with automatic documentation
- Bulk operations support
- Data export capabilities
- Health monitoring endpoints

### Environment Configuration

Create a `.env` file with the following variables:

```env
# Azure Speech Services
SPEECH_ENDPOINT=https://westus2.api.cognitive.microsoft.com
SPEECH_SUBSCRIPTION_KEY=your_speech_subscription_key
API_VERSION=2024-04-15-preview

# Azure OpenAI (for translations and recommendations)
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_openai_api_key
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name

# Azure Cosmos DB (MongoDB API)
AZCOSMOS_CONNSTR=mongodb://your-cosmos-account:your-primary-key@your-cosmos-account.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@your-cosmos-account@
AZCOSMOS_DATABASE_NAME_Batch=avatarbatch
AZCOSMOS_CONTAINER_NAME_batch=avatarbatch

# Avatar Background Images (Azure Blob Storage URLs)
BACKGROUND_IMAGE_Binaka_URL=https://aiavatar123.blob.core.windows.net/aiavatar/Binaka_background.jpg
BACKGROUND_IMAGE_sri_URL=https://aiavatar123.blob.core.windows.net/aiavatar/Sri_background.jpg
BACKGROUND_IMAGE_mike_URL=https://aiavatar123.blob.core.windows.net/aiavatar/Mike_background.jpg

# Analytics Configuration
ENABLE_ANALYTICS=true
```

### Database Schema

#### User Engagements Collection
```json
{
  "_id": "ObjectId",
  "engagement_id": "uuid",
  "username": "string",
  "customer_name": "string",
  "company_name": "string",
  "industry": "string",
  "avatar_name": "string",
  "language": "string",
  "text_input": "string",
  "video_url": "string",
  "tokens_used": "integer",
  "words_count": "integer",
  "session_id": "string",
  "ip_address": "string",
  "user_agent": "string",
  "timestamp": "ISO 8601 datetime",
  "processing_time_seconds": "float",
  "video_duration_seconds": "float",
  "application_source": "string"
}
```

#### Global Metrics Collection
```json
{
  "_id": "global_metrics",
  "total_videos_generated": "integer",
  "total_engagements": "integer",
  "total_tokens_consumed": "integer",
  "total_users": "integer",
  "active_users_today": "integer",
  "active_users_this_week": "integer",
  "active_users_this_month": "integer",
  "videos_by_avatar": "object",
  "videos_by_language": "object",
  "videos_by_industry": "object",
  "engagement_by_day": "object",
  "last_updated": "ISO 8601 datetime"
}
```

#### User Profiles Collection
```json
{
  "_id": "ObjectId",
  "username": "string",
  "total_engagements": "integer",
  "total_tokens": "integer",
  "total_words": "integer",
  "first_engagement": "ISO 8601 datetime",
  "last_active": "ISO 8601 datetime",
  "last_customer_name": "string",
  "last_company_name": "string",
  "last_industry": "string",
  "last_avatar_used": "string",
  "last_language_used": "string",
  "last_application_source": "string",
  "created_date": "ISO 8601 datetime"
}
```

### Deployment Instructions

#### 1. Azure Cosmos DB Setup
1. Create Azure Cosmos DB account with MongoDB API
2. Create database: `avatarbatch`
3. Collections will be auto-created by the application
4. Copy connection string to environment variables

#### 2. Streamlit Application Deployment
```bash
# Install dependencies
pip install streamlit plotly pandas pymongo python-dotenv openai requests

# Run application
streamlit run enhanced_streamlit_app.py --server.port 8501
```

#### 3. HTML Application Deployment
- Deploy `enhanced_html_avatar_app.html` to web server
- Ensure CORS is properly configured for API access
- Update API endpoints if using remote analytics API

#### 4. Analytics API Deployment
```bash
# Install dependencies
pip install fastapi uvicorn pymongo python-dotenv

# Run API server
uvicorn analytics_api:app --host 0.0.0.0 --port 8000 --reload
```

#### 5. Docker Deployment (Optional)
```dockerfile
# Dockerfile for Analytics API
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "analytics_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### API Endpoints

#### Core Endpoints
- `GET /` - API information
- `GET /health` - Health check
- `GET /config` - Configuration status

#### Analytics Endpoints
- `POST /engagement` - Save new engagement
- `GET /metrics/global` - Get global metrics
- `GET /user/{username}/stats` - Get user statistics
- `GET /dashboard` - Get dashboard data
- `GET /analytics/trends?days=30` - Get trends analysis
- `POST /analytics/bulk-engagement` - Bulk save engagements

#### Management Endpoints
- `DELETE /user/{username}/reset` - Reset user metrics
- `GET /analytics/export/{username}` - Export user data

### Integration Examples

#### Streamlit Integration
```python
from global_avatar_analytics import GlobalAvatarAnalytics, create_engagement_from_streamlit_data

# Initialize analytics
analytics = GlobalAvatarAnalytics(connection_string, database_name)

# Save engagement
engagement = create_engagement_from_streamlit_data(
    username="john_doe",
    customer_name="John Doe",
    avatar_name="Binaka-AI GBB Leader",
    language="English",
    text_input="Hello world",
    video_url="https://example.com/video.mp4",
    tokens_used=15,
    industry="healthcare"
)

success = analytics.save_engagement(engagement)
```

#### HTML/JavaScript Integration
```javascript
// Save engagement via API
async function saveEngagement(engagementData) {
    const response = await fetch('/engagement', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(engagementData)
    });
    return response.json();
}

// Get global metrics
async function getGlobalMetrics() {
    const response = await fetch('/metrics/global');
    return response.json();
}
```

### Monitoring and Maintenance

#### Key Metrics to Monitor
- Total videos generated (growth rate)
- Active users (daily, weekly, monthly)
- Token consumption (cost tracking)
- Error rates and processing times
- Popular avatars and languages
- Industry engagement patterns

#### Database Maintenance
- Monitor collection sizes and performance
- Set up automated backups
- Configure appropriate indexing
- Consider partitioning for large datasets

#### Performance Optimization
- Use connection pooling for database connections
- Implement caching for frequently accessed metrics
- Consider read replicas for high-traffic scenarios
- Monitor and optimize query performance

### Security Considerations

#### Data Protection
- Encrypt sensitive data at rest and in transit
- Implement proper access controls
- Regular security audits
- GDPR/privacy compliance measures

#### API Security
- Implement rate limiting
- Use API keys or OAuth for authentication
- Input validation and sanitization
- Monitor for suspicious activities

### Troubleshooting

#### Common Issues
1. **Analytics not working**: Check AZCOSMOS_CONNSTR environment variable
2. **Metrics not updating**: Verify database connectivity
3. **Performance issues**: Check database indexes and query optimization
4. **Memory issues**: Monitor connection pool sizes

#### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Future Enhancements

#### Planned Features
- Real-time analytics dashboard with WebSocket updates
- Advanced ML-powered insights and predictions
- Integration with Azure Application Insights
- Custom reporting and data visualization
- Multi-tenant support for enterprise deployments

#### Scalability Improvements
- Implement data archiving strategies
- Add support for analytics data lakes
- Implement distributed caching
- Consider event-driven architecture

### Support and Documentation

#### API Documentation
- FastAPI auto-generates documentation at `/docs`
- Interactive API testing available at `/redoc`

#### Contact Information
- Technical Support: ganac@microsoft.com
- Documentation: Internal AI-GBB Team Wiki
- Issue Tracking: Azure DevOps Project

---

## Quick Start Guide

1. **Set up Azure Cosmos DB** with MongoDB API
2. **Configure environment variables** in `.env` file
3. **Install dependencies**: `pip install -r requirements.txt`
4. **Run Streamlit app**: `streamlit run enhanced_streamlit_app.py`
5. **Start API server**: `uvicorn analytics_api:app --reload`
6. **Access analytics** at `http://localhost:8501` and `http://localhost:8000/docs`

Your global analytics system is now ready to track engagement across all AI Avatar applications!
