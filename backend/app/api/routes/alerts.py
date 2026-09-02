from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.dependencies import get_db
from app.api.schemas.alert import AlertResponse, AlertAcknowledgeRequest
from app.db import crud

router = APIRouter()

@router.get("", response_model=List[AlertResponse])
async def list_alerts(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    return await crud.get_alerts(db, skip=skip, limit=limit)

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    alert = await crud.get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    request: AlertAcknowledgeRequest,
    db: AsyncSession = Depends(get_db)
):
    alert = await crud.acknowledge_alert(db, alert_id, request.action_taken)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
    return alert
