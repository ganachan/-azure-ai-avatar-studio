"""
AI Avatar Analytics API
FastAPI backend service for managing global analytics and engagement tracking
Supports both Streamlit and HTML applications
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import os
import logging
from datetime import datetime, timedelta, timezone
import uvicorn
from contextlib import asynccontextmanager

# Import our analytics system
from global_avatar_analytics import (
    GlobalAvatarAnalytics, 
    UserEngagement, 
    GlobalMetrics,
    create_engagement_from_streamlit_data,
    create_engagement_from_html_data,
    get_analytics_config
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global analytics instance
analytics_system: Optional[GlobalAvatarAnalytics] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize analytics system on startup"""
    global analytics_system
    
    try:
        config = get_analytics_config()
        if config["connection_string"] and config["enable_analytics"]:
            analytics_system = GlobalAvatarAnalytics(
                connection_string=config["connection_string"],
                database_name=config["database_name"]
            )
            logger.info("Analytics system initialized successfully")
        else:
            logger.warning("Analytics system not initialized - missing configuration")
    except Exception as e:
        logger.error(f"Failed to initialize analytics system: {str(e)}")
    
    yield
    
    # Cleanup on shutdown
    if analytics_system and hasattr(analytics_system, 'client'):
        try:
            analytics_system.client.close()
            logger.info("Analytics system closed")
        except Exception as e:
            logger.error(f"Error closing analytics system: {str(e)}")

# Create FastAPI app
app = FastAPI(
    title="AI Avatar Analytics API",
    description="Global analytics and engagement tracking for AI Avatar applications",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class EngagementRequest(BaseModel):
    username: str = Field(..., description="Username")
    customer_name: str = Field(..., description="Customer name")
    company_name: Optional[str] = Field("", description="Company name")
    industry: Optional[str] = Field("", description="Industry")
    avatar_name: str = Field(..., description="Avatar used")
    language: str = Field(..., description="Language used")
    text_input: str = Field(..., description="Input text")
    video_url: Optional[str] = Field("", description="Generated video URL")
    tokens_used: Optional[int] = Field(0, description="Tokens consumed")
    session_id: Optional[str] = Field("", description="Session ID")
    application_source: Optional[str] = Field("api", description="Source application")
    processing_time_seconds: Optional[float] = Field(0, description="Processing time")
    video_duration_seconds: Optional[float] = Field(0, description="Video duration")

class EngagementResponse(BaseModel):
    success: bool
    engagement_id: str
    message: str

class GlobalMetricsResponse(BaseModel):
    total_videos_generated: int
    total_users: int
    active_users_today: int
    active_users_this_week: int
    active_users_this_month: int
    total_tokens_consumed: int
    videos_by_avatar: Dict[str, int]
    videos_by_language: Dict[str, int]
    videos_by_industry: Dict[str, int]
    engagement_by_day: Dict[str, int]
    last_updated: str

class UserStatsResponse(BaseModel):
    total_engagements: int
    total_tokens: int
    total_words: int
    first_engagement: str
    last_active: str
    favorite_avatar: str
    favorite_language: str
    engagement_streak: int
    recent_engagements: List[Dict[str, Any]]

class DashboardDataResponse(BaseModel):
    global_metrics: GlobalMetricsResponse
    top_users: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]
    growth_trends: Dict[str, Any]
    industry_breakdown: Dict[str, int]
    performance_metrics: Dict[str, Any]
    last_updated: str

class HealthResponse(BaseModel):
    status: str
    analytics_available: bool
    timestamp: str

# Dependency to get analytics system
def get_analytics():
    if analytics_system is None:
        raise HTTPException(
            status_code=503,
            detail="Analytics system not available. Please check configuration."
        )
    return analytics_system

# API Routes

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Avatar Analytics API",
        "version": "1.0.0",
        "documentation": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        analytics_available=analytics_system is not None,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

@app.post("/engagement", response_model=EngagementResponse)
async def save_engagement(
    engagement_data: EngagementRequest,
    background_tasks: BackgroundTasks,
    analytics: GlobalAvatarAnalytics = Depends(get_analytics)
):
    """Save a new engagement to the analytics system"""
    try:
        # Create engagement object
        engagement = UserEngagement(
            engagement_id="",  # Will be auto-generated
            username=engagement_data.username,
            customer_name=engagement_data.customer_name,
            company_name=engagement_data.company_name,
            industry=engagement_data.industry,
            avatar_name=engagement_data.avatar_name,
            language=engagement_data.language,
            text_input=engagement_data.text_input,
            video_url=engagement_data.video_url,
            tokens_used=engagement_data.tokens_used,
            words_count=len(engagement_data.text_input.split()) if engagement_data.text_input else 0,
            session_id=engagement_data.session_id,
            application_source=engagement_data.application_source,
            processing_time_seconds=engagement_data.processing_time_seconds,
            video_duration_seconds=engagement_data.video_duration_seconds
        )
        
        # Save engagement
        success = analytics.save_engagement(engagement)
        
        if success:
            return EngagementResponse(
                success=True,
                engagement_id=engagement.engagement_id,
                message="Engagement saved successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save engagement")
            
    except Exception as e:
        logger.error(f"Error saving engagement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/metrics/global", response_model=GlobalMetricsResponse)
async def get_global_metrics(analytics: GlobalAvatarAnalytics = Depends(get_analytics)):
    """Get global platform metrics"""
    try:
        metrics = analytics.get_global_metrics()
        
        return GlobalMetricsResponse(
            total_videos_generated=metrics.total_videos_generated,
            total_users=metrics.total_users,
            active_users_today=metrics.active_users_today,
            active_users_this_week=metrics.active_users_this_week,
            active_users_this_month=metrics.active_users_this_month,
            total_tokens_consumed=metrics.total_tokens_consumed,
            videos_by_avatar=metrics.videos_by_avatar,
            videos_by_language=metrics.videos_by_language,
            videos_by_industry=metrics.videos_by_industry,
            engagement_by_day=metrics.engagement_by_day,
            last_updated=metrics.last_updated
        )
        
    except Exception as e:
        logger.error(f"Error getting global metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/user/{username}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    username: str,
    analytics: GlobalAvatarAnalytics = Depends(get_analytics)
):
    """Get user-specific statistics"""
    try:
        stats = analytics.get_user_stats(username)
        
        if "error" in stats:
            raise HTTPException(status_code=404, detail=f"User not found or error: {stats['error']}")
        
        return UserStatsResponse(
            total_engagements=stats['total_engagements'],
            total_tokens=stats['total_tokens'],
            total_words=stats['total_words'],
            first_engagement=stats['first_engagement'],
            last_active=stats['last_active'],
            favorite_avatar=stats['favorite_avatar'],
            favorite_language=stats['favorite_language'],
            engagement_streak=stats['engagement_streak'],
            recent_engagements=stats['recent_engagements']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(analytics: GlobalAvatarAnalytics = Depends(get_analytics)):
    """Get comprehensive dashboard data"""
    try:
        dashboard_data = analytics.get_analytics_dashboard_data()
        
        if "error" in dashboard_data:
            raise HTTPException(status_code=500, detail=f"Dashboard error: {dashboard_data['error']}")
        
        global_metrics = dashboard_data["global_metrics"]
        
        return DashboardDataResponse(
            global_metrics=GlobalMetricsResponse(**global_metrics),
            top_users=dashboard_data["top_users"],
            recent_activity=dashboard_data["recent_activity"],
            growth_trends=dashboard_data["growth_trends"],
            industry_breakdown=dashboard_data["industry_breakdown"],
            performance_metrics=dashboard_data["performance_metrics"],
            last_updated=dashboard_data["last_updated"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/user/{username}/reset")
async def reset_user_metrics(
    username: str,
    analytics: GlobalAvatarAnalytics = Depends(get_analytics)
):
    """Reset a user's metrics (use with caution)"""
    try:
        success = analytics.reset_user_metrics(username)
        
        if success:
            return {"success": True, "message": f"Metrics reset for user: {username}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset user metrics")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting user metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/analytics/export/{username}")
async def export_user_data(
    username: str,
    analytics: GlobalAvatarAnalytics = Depends(get_analytics)
):
    """Export user's engagement data"""
    try:
        # Get all user engagements
        user_engagements = list(analytics.engagements_collection.find(
            {"username": username},
            {"_id": 0}  # Exclude MongoDB _id field
        ))
        
        if not user_engagements:
            raise HTTPException(status_code=404, detail="No data found for user")
        
        return {
            "username": username,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "total_engagements": len(user_engagements),
            "engagements": user_engagements
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting user data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/analytics/trends")
async def get_analytics_trends(
    days: int = 30,
    analytics: GlobalAvatarAnalytics = Depends(get_analytics)
):
    """Get analytics trends for specified number of days"""
    try:
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Get engagements in date range
        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$dateFromString": {"dateString": "$timestamp"}}}},
                        "avatar": "$avatar_name",
                        "language": "$language",
                        "industry": "$industry"
                    },
                    "count": {"$sum": 1},
                    "tokens": {"$sum": "$tokens_used"}
                }
            },
            {"$sort": {"_id.date": 1}}
        ]
        
        trends_data = list(analytics.engagements_collection.aggregate(pipeline))
        
        # Process data for response
        daily_totals = {}
        avatar_trends = {}
        language_trends = {}
        industry_trends = {}
        
        for item in trends_data:
            date = item["_id"]["date"]
            avatar = item["_id"]["avatar"]
            language = item["_id"]["language"]
            industry = item["_id"]["industry"]
            count = item["count"]
            tokens = item["tokens"]
            
            # Daily totals
            if date not in daily_totals:
                daily_totals[date] = {"engagements": 0, "tokens": 0}
            daily_totals[date]["engagements"] += count
            daily_totals[date]["tokens"] += tokens
            
            # Avatar trends
            if avatar not in avatar_trends:
                avatar_trends[avatar] = {}
            if date not in avatar_trends[avatar]:
                avatar_trends[avatar][date] = 0
            avatar_trends[avatar][date] += count
            
            # Language trends
            if language not in language_trends:
                language_trends[language] = {}
            if date not in language_trends[language]:
                language_trends[language][date] = 0
            language_trends[language][date] += count
            
            # Industry trends
            if industry and industry not in industry_trends:
                industry_trends[industry] = {}
            if industry and date not in industry_trends[industry]:
                industry_trends[industry][date] = 0
            if industry:
                industry_trends[industry][date] += count
        
        return {
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "daily_totals": daily_totals,
            "avatar_trends": avatar_trends,
            "language_trends": language_trends,
            "industry_trends": industry_trends
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics trends: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/analytics/bulk-engagement")
async def bulk_save_engagements(
    engagements: List[EngagementRequest],
    background_tasks: BackgroundTasks,
    analytics: GlobalAvatarAnalytics = Depends(get_analytics)
):
    """Save multiple engagements in bulk"""
    try:
        saved_count = 0
        failed_count = 0
        engagement_ids = []
        
        for engagement_data in engagements:
            try:
                engagement = UserEngagement(
                    engagement_id="",
                    username=engagement_data.username,
                    customer_name=engagement_data.customer_name,
                    company_name=engagement_data.company_name,
                    industry=engagement_data.industry,
                    avatar_name=engagement_data.avatar_name,
                    language=engagement_data.language,
                    text_input=engagement_data.text_input,
                    video_url=engagement_data.video_url,
                    tokens_used=engagement_data.tokens_used,
                    words_count=len(engagement_data.text_input.split()) if engagement_data.text_input else 0,
                    session_id=engagement_data.session_id,
                    application_source=engagement_data.application_source,
                    processing_time_seconds=engagement_data.processing_time_seconds,
                    video_duration_seconds=engagement_data.video_duration_seconds
                )
                
                success = analytics.save_engagement(engagement)
                if success:
                    saved_count += 1
                    engagement_ids.append(engagement.engagement_id)
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error saving individual engagement: {str(e)}")
                failed_count += 1
        
        return {
            "total_processed": len(engagements),
            "saved": saved_count,
            "failed": failed_count,
            "engagement_ids": engagement_ids
        }
        
    except Exception as e:
        logger.error(f"Error in bulk save: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Configuration endpoints
@app.get("/config")
async def get_configuration():
    """Get API configuration information"""
    config = get_analytics_config()
    
    return {
        "analytics_enabled": config["enable_analytics"],
        "database_configured": bool(config["connection_string"]),
        "database_name": config["database_name"]
    }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.now(timezone.utc).isoformat()}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "timestamp": datetime.now(timezone.utc).isoformat()}
    )

# Main function to run the server
if __name__ == "__main__":
    uvicorn.run(
        "analytics_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )