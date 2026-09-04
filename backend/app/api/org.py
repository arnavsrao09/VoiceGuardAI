from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db import crud
from app.db.models import Organization, DetectionSession, Alert
from app.api.deps import get_current_org, hash_api_key
from pydantic import BaseModel
from typing import List
import uuid
from datetime import datetime, timezone
import secrets
from sqlalchemy.future import select
from sqlalchemy import func
from app.api import schemas

router = APIRouter()

class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    key: str = None  # Only returned once on creation
    prefix: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class ApiKeyListResponse(BaseModel):
    id: uuid.UUID
    prefix: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class OrgDashboardStats(BaseModel):
    total_sessions: int
    total_alerts: int
    critical_alerts: int

@router.post("/keys", response_model=ApiKeyResponse)
async def create_key(org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    # Generate a 64 character hex key
    raw_key = secrets.token_hex(32)
    key_hash = hash_api_key(raw_key)
    prefix = raw_key[:8] + "..."
    
    api_key_record = await crud.create_api_key(db, organization_id=org.id, key_hash=key_hash, prefix=prefix)
    
    # We return the raw key only this one time
    return {
        "id": api_key_record.id,
        "key": raw_key,
        "prefix": api_key_record.prefix,
        "is_active": api_key_record.is_active,
        "created_at": api_key_record.created_at
    }

@router.get("/keys", response_model=List[ApiKeyListResponse])
async def list_keys(org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    keys = await crud.get_api_keys_for_org(db, org.id)
    return keys

@router.delete("/keys/{key_id}")
async def revoke_key(key_id: uuid.UUID, org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    success = await crud.revoke_api_key(db, key_id, org.id)
    if not success:
        raise HTTPException(status_code=404, detail="API Key not found or already revoked")
    return {"detail": "API Key revoked successfully"}

@router.get("/dashboard/stats", response_model=OrgDashboardStats)
async def get_dashboard_stats(org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    # Total sessions
    sessions_result = await db.execute(select(func.count(DetectionSession.session_id)).filter(DetectionSession.organization_id == org.id))
    total_sessions = sessions_result.scalar() or 0
    
    # Total alerts
    alerts_result = await db.execute(select(func.count(Alert.id)).filter(Alert.organization_id == org.id))
    total_alerts = alerts_result.scalar() or 0
    
    # Critical alerts
    critical_result = await db.execute(select(func.count(Alert.id)).filter(Alert.organization_id == org.id, Alert.severity == "CRITICAL"))
    critical_alerts = critical_result.scalar() or 0
    
    return OrgDashboardStats(
        total_sessions=total_sessions,
        total_alerts=total_alerts,
        critical_alerts=critical_alerts
    )

@router.get("/sessions", response_model=List[schemas.DetectionSessionResponse])
async def list_org_sessions(org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    """List detection sessions for this organization on the dashboard."""
    return await crud.get_all_sessions(db, organization_id=org.id)

@router.get("/speakers", response_model=List[schemas.SpeakerProfileResponse])
async def list_org_speakers(org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    """List speaker profiles for this organization."""
    return await crud.get_all_voice_profiles(db, organization_id=org.id)
