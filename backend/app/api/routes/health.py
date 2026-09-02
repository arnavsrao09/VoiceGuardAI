from fastapi import APIRouter
from app.ml.model_manager import model_manager
from app.db.database import check_db_connection
from redis.asyncio import Redis
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    # Check DB
    db_status = await check_db_connection()
    
    # Check Redis
    try:
        redis_client = Redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        redis_status = True
        await redis_client.close()
    except Exception:
        redis_status = False

    return {
        "status": "healthy" if db_status and redis_status else "degraded",
        "models": model_manager.get_status(),
        "device": model_manager.get_device(),
        "database": "connected" if db_status else "disconnected",
        "redis": "connected" if redis_status else "disconnected"
    }
