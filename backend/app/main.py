from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.ml.model_manager import model_manager

# Setup logging before anything else
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend for AI-powered real-time voice cloning detection system"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up VoiceGuardAI Backend...")
    # Initialize models
    model_manager.initialize()
    logger.info("Models initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

# Include routers
from app.api.routes import health, analysis, speakers, sessions, alerts, config
from app.api.websocket import router as ws_router

app.include_router(health.router, prefix=settings.API_PREFIX, tags=["Health"])
app.include_router(analysis.router, prefix=f"{settings.API_PREFIX}", tags=["Analysis"])
app.include_router(speakers.router, prefix=f"{settings.API_PREFIX}/speakers", tags=["Speakers"])
app.include_router(sessions.router, prefix=f"{settings.API_PREFIX}/sessions", tags=["Sessions"])
app.include_router(alerts.router, prefix=f"{settings.API_PREFIX}/alerts", tags=["Alerts"])
app.include_router(config.router, prefix=f"{settings.API_PREFIX}/config", tags=["Configuration"])
app.include_router(ws_router, prefix=f"{settings.API_PREFIX}/ws", tags=["WebSocket"])

# Other routers will be included here as they are developed
