from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import rest, websocket, auth, org, b2b, telephony
from .ml.pipeline import InferencePipeline
from .db.database import engine, Base, db_dialect
import app.db.models
from sqlalchemy import text
from .api import privacy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.privacy.retention import DataRetentionManager
from app.db.database import AsyncSessionLocal
from app.logging_config import setup_logging, get_logger

logger = get_logger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    # Startup: Initialize DB
    try:
        async with engine.begin() as conn:
            if db_dialect == "postgresql":
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                except Exception as e:
                    logger.debug("pgvector extension creation skipped: %s", e)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables and extensions verified.")
    except Exception as e:
        logger.warning("DB init warning (continuing): %s", e)

    # Startup: Start APScheduler for background tasks
    scheduler = AsyncIOScheduler()
    
    async def scheduled_purge_job():
        try:
            async with AsyncSessionLocal() as db:
                logger.debug("Running scheduled privacy data purge...")
                purged = await DataRetentionManager.run_scheduled_purge(db)
                logger.debug("Purge complete: %s", purged)
        except Exception as e:
            logger.warning("Error in scheduled purge: %s", e)
            
    scheduler.add_job(
        scheduled_purge_job, 
        'interval', 
        hours=settings.privacy_purge_interval_hours,
        id='privacy_purge'
    )
    scheduler.start()

    # Startup: Load models and warmup
    pipeline = InferencePipeline.get_instance()
    pipeline.warmup()

    # Startup: Start SIP/VoIP PBX gateway
    try:
        from .telephony.sip_server import start_sip_server
        await start_sip_server()
        logger.info("SIP gateway started on port 5060.")
    except Exception as e:
        logger.warning("SIP server start warning: %s", e)

    # Startup: Start Asterisk ARI bridge (non-blocking, reconnects automatically)
    try:
        from .telephony.asterisk_bridge import asterisk_bridge
        await asterisk_bridge.start()
        logger.info("Asterisk ARI bridge started.")
    except Exception as e:
        logger.debug("Asterisk bridge not started (non-critical): %s", e)

    yield
    # Shutdown: Clean up if needed
    scheduler.shutdown(wait=False)
    pass

app = FastAPI(
    title=settings.app_name,
    description="Real-Time Voice Cloning Detection & Prevention Framework API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(org.router, prefix="/api/v1/org")
app.include_router(b2b.router, prefix="/api/v1/b2b")
app.include_router(rest.router, prefix="/api/v1")
app.include_router(telephony.router, prefix="/api/v1/telephony")
app.include_router(privacy.router, prefix="/api/v1/privacy")
app.include_router(websocket.router)

@app.get("/")
async def root():
    return {"message": "Welcome to VoiceGuardAI API", "status": "active"}

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
