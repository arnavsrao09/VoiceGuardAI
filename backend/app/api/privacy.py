import uuid
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.db.database import get_db
from app.privacy.anonymizer import PrivacyAnonymizer, InferenceMode
from app.privacy.retention import DataRetentionManager
from app.privacy.audit import get_audit_log, log_privacy_event
from app.api.deps import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError

router = APIRouter()

def _extract_org_id_from_request(request: Request) -> uuid.UUID | None:
    """Optionally extract organization_id from JWT Bearer token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        org_id_str = payload.get("sub")
        if org_id_str:
            return uuid.UUID(org_id_str)
    except (JWTError, ValueError):
        pass
    return None

def get_org_id_or_401(request: Request) -> uuid.UUID:
    org_id = _extract_org_id_from_request(request)
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return org_id

@router.get("/status")
async def get_privacy_status(request: Request, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    config = await DataRetentionManager.get_retention_config(db, org_id)
    inventory = await DataRetentionManager.get_data_inventory(db, org_id)
    return {
        "privacy_mode": PrivacyAnonymizer.is_privacy_mode_enabled(),
        "inference_mode": config.inference_mode,
        "retention_config": {
            "session_ttl_days": config.session_ttl_days,
            "telemetry_ttl_days": config.telemetry_ttl_days,
            "embedding_ttl_days": config.embedding_ttl_days,
            "alert_ttl_days": config.alert_ttl_days
        },
        "inventory": inventory
    }

@router.post("/mode")
async def toggle_privacy_mode(request: Request, enabled: bool = True, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    PrivacyAnonymizer.set_privacy_mode(enabled)
    
    await log_privacy_event(
        db,
        "PRIVACY_MODE_CHANGED",
        {"enabled": enabled},
        org_id
    )
    
    return {
        "privacy_mode": enabled,
        "mode_description": "Edge/RAM-Only Stream Extraction (Zero Audio Persistence)" if enabled else "Cloud Audit Mode"
    }

class RetentionUpdateRequest(BaseModel):
    session_ttl_days: Optional[float] = None
    telemetry_ttl_days: Optional[float] = None
    embedding_ttl_days: Optional[float] = None
    alert_ttl_days: Optional[float] = None
    inference_mode: Optional[str] = None

@router.put("/retention")
async def update_retention_config(request: Request, body: RetentionUpdateRequest, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    update_data = body.model_dump(exclude_unset=True)
    
    if "inference_mode" in update_data:
        try:
            InferenceMode(update_data["inference_mode"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid inference mode")

    config = await DataRetentionManager.update_retention_config(db, org_id, **update_data)
    return config

@router.post("/purge")
async def manual_purge(request: Request, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    config = await DataRetentionManager.get_retention_config(db, org_id)
    
    s_count = await DataRetentionManager.purge_expired_sessions(db, org_id, config.session_ttl_days)
    t_count = await DataRetentionManager.purge_expired_telemetry(db, org_id, config.telemetry_ttl_days)
    e_count = await DataRetentionManager.purge_expired_embeddings(db, org_id, config.embedding_ttl_days)
    a_count = await DataRetentionManager.purge_expired_alerts(db, org_id, config.alert_ttl_days)
    
    await db.commit()
    
    purged_counts = {
        "sessions": s_count,
        "telemetry": t_count,
        "embeddings_nullified": e_count,
        "alerts": a_count
    }
    
    await log_privacy_event(
        db,
        "DATA_PURGE_COMPLETED",
        {
            "purged": purged_counts,
            "trigger": "manual_request"
        },
        org_id
    )
    
    return {"status": "success", "purged": purged_counts}

@router.post("/erasure")
async def right_to_erasure(request: Request, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    await DataRetentionManager.erase_organization_data(db, org_id)
    return {"status": "success", "message": "All organizational data has been permanently erased."}

@router.get("/audit-log")
async def view_audit_log(request: Request, limit: int = 100, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    entries = await get_audit_log(db, org_id, limit)
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "details": e.details,
            "created_at": e.created_at.isoformat()
        } for e in entries
    ]

@router.get("/compliance-report")
async def export_compliance_report(request: Request, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    config = await DataRetentionManager.get_retention_config(db, org_id)
    inventory = await DataRetentionManager.get_data_inventory(db, org_id)
    audit_entries = await get_audit_log(db, org_id, 1000)
    
    # Format config to dict
    config_dict = {
        "session_ttl_days": config.session_ttl_days,
        "telemetry_ttl_days": config.telemetry_ttl_days,
        "embedding_ttl_days": config.embedding_ttl_days,
        "alert_ttl_days": config.alert_ttl_days,
        "inference_mode": config.inference_mode
    }
    
    await log_privacy_event(
        db,
        "COMPLIANCE_REPORT_EXPORTED",
        {"status": "success"},
        org_id
    )
    
    return PrivacyAnonymizer.generate_compliance_report(
        data_inventory=inventory,
        retention_config=config_dict,
        audit_entries=len(audit_entries)
    )

@router.get("/data-inventory")
async def get_data_inventory(request: Request, db: AsyncSession = Depends(get_db)):
    org_id = get_org_id_or_401(request)
    return await DataRetentionManager.get_data_inventory(db, org_id)
