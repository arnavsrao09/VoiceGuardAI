from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import rest, websocket
from .ml.pipeline import InferencePipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load models and warmup
    pipeline = InferencePipeline.get_instance()
    pipeline.warmup()
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

app.include_router(rest.router, prefix="/api/v1")
app.include_router(websocket.router)

@app.get("/")
async def root():
    return {"message": "Welcome to VoiceSentinel API", "status": "active"}

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
