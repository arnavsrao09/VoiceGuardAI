from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.dependencies import get_db
from app.api.schemas.session import SessionResponse, SessionTimelineItem
from app.db import crud

router = APIRouter()

@router.post("", response_model=SessionResponse)
async def create_session(caller_id: UUID = None, db: AsyncSession = Depends(get_db)):
    session = await crud.create_session(db, caller_id)
    return session

@router.get("", response_model=List[SessionResponse])
async def list_sessions(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    return await crud.get_sessions(db, skip=skip, limit=limit)

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/{session_id}/timeline", response_model=List[SessionTimelineItem])
async def get_session_timeline(session_id: UUID, db: AsyncSession = Depends(get_db)):
    # Check if session exists first
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    timeline = await crud.get_session_timeline(db, session_id)
    return timeline

@router.post("/{session_id}/complete", response_model=SessionResponse)
async def complete_session(session_id: UUID, avg_risk_score: float = 0.0, db: AsyncSession = Depends(get_db)):
    session = await crud.complete_session(db, session_id, avg_risk_score)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
