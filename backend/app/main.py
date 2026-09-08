from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import rest, websocket, auth, org, b2b, telephony
from .ml.pipeline import InferencePipeline
from .db.database import engine, Base, db_dialect
import app.db.models
from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB
    try:
        async with engine.begin() as conn:
            if db_dialect == "postgresql":
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                except Exception as e:
                    print(f"[DB] pgvector extension creation skipped: {e}")
            await conn.run_sync(Base.metadata.create_all)
        print("[DB] Tables and extensions verified successfully.")
    except Exception as e:
        print(f"[DB] Initialization warning (continuing startup): {e}")

    # Startup: Load models and warmup
    pipeline = InferencePipeline.get_instance()
    pipeline.warmup()

    # Startup: Start SIP/VoIP PBX gateway
    try:
        from .telephony.sip_server import start_sip_server
        await start_sip_server()
        print("[SIP] VoiceGuard SIP gateway started on port 5060.")
    except Exception as e:
        print(f"[SIP] Warning starting SIP server: {e}")

    yield
    # Shutdown: Clean up if needed
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
app.include_router(websocket.router)

@app.get("/")
async def root():
    return {"message": "Welcome to VoiceGuardAI API", "status": "active"}

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
