from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional

from app.db.models import VoiceProfile, DetectionSession, RiskTelemetry, Alert, AuditLog

# Voice Profiles
async def create_voice_profile(db: AsyncSession, name: str, language: str, embedding: list) -> VoiceProfile:
    profile = VoiceProfile(name=name, language=language, embedding=embedding)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile

async def get_voice_profiles(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[VoiceProfile]:
    result = await db.execute(select(VoiceProfile).offset(skip).limit(limit))
    return result.scalars().all()

async def get_voice_profile(db: AsyncSession, profile_id: UUID) -> Optional[VoiceProfile]:
    result = await db.execute(select(VoiceProfile).where(VoiceProfile.id == profile_id))
    return result.scalars().first()

async def delete_voice_profile(db: AsyncSession, profile_id: UUID) -> bool:
    profile = await get_voice_profile(db, profile_id)
    if profile:
        await db.delete(profile)
        await db.commit()
        return True
    return False

# Detection Sessions
async def create_session(db: AsyncSession, caller_id: Optional[UUID] = None) -> DetectionSession:
    session = DetectionSession(caller_id=caller_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def get_session(db: AsyncSession, session_id: UUID) -> Optional[DetectionSession]:
    result = await db.execute(select(DetectionSession).where(DetectionSession.id == session_id))
    return result.scalars().first()

async def get_sessions(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DetectionSession]:
    result = await db.execute(select(DetectionSession).order_by(DetectionSession.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()

async def complete_session(db: AsyncSession, session_id: UUID, avg_risk_score: float) -> Optional[DetectionSession]:
    session = await get_session(db, session_id)
    if session:
        session.end_time = datetime.now(timezone.utc)
        session.status = "completed"
        session.avg_risk_score = avg_risk_score
        await db.commit()
        await db.refresh(session)
    return session

# Risk Telemetry
async def create_telemetry(db: AsyncSession, telemetry_data: dict) -> RiskTelemetry:
    telemetry = RiskTelemetry(**telemetry_data)
    db.add(telemetry)
    await db.commit()
    await db.refresh(telemetry)
    return telemetry

async def get_session_timeline(db: AsyncSession, session_id: UUID) -> List[RiskTelemetry]:
    result = await db.execute(select(RiskTelemetry).where(RiskTelemetry.session_id == session_id).order_by(RiskTelemetry.chunk_index))
    return result.scalars().all()

# Alerts
async def create_alert(db: AsyncSession, alert_data: dict) -> Alert:
    alert = Alert(**alert_data)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert

async def get_alerts(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Alert]:
    result = await db.execute(select(Alert).order_by(Alert.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()

async def get_alert(db: AsyncSession, alert_id: UUID) -> Optional[Alert]:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    return result.scalars().first()

async def acknowledge_alert(db: AsyncSession, alert_id: UUID, action_taken: str = None) -> Optional[Alert]:
    alert = await get_alert(db, alert_id)
    if alert and not alert.acknowledged:
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.action_taken = action_taken
        await db.commit()
        await db.refresh(alert)
    return alert
