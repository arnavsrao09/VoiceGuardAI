from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import VoiceProfile, DetectionSession, RiskTelemetry, Alert
from pgvector.sqlalchemy import Vector
import uuid

async def create_voice_profile(db: AsyncSession, user_id: str, name: str, embedding: list[float], language: str = "en"):
    db_profile = VoiceProfile(
        user_id=user_id,
        name=name,
        embedding=embedding,
        language=language
    )
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return db_profile

async def get_voice_profile(db: AsyncSession, profile_id: uuid.UUID):
    result = await db.execute(select(VoiceProfile).filter(VoiceProfile.id == profile_id))
    return result.scalars().first()

async def create_detection_session(db: AsyncSession, caller_id: str):
    session = DetectionSession(caller_id=caller_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def add_risk_telemetry(db: AsyncSession, session_id: uuid.UUID, telemetry_data: dict):
    telemetry = RiskTelemetry(session_id=session_id, **telemetry_data)
    db.add(telemetry)
    await db.commit()
    return telemetry

async def create_alert(db: AsyncSession, session_id: uuid.UUID, severity: str, trigger_reason: str, risk_score: float):
    alert = Alert(
        session_id=session_id,
        severity=severity,
        trigger_reason=trigger_reason,
        risk_score=risk_score
    )
    db.add(alert)
    await db.commit()
    return alert

async def get_all_voice_profiles(db: AsyncSession):
    result = await db.execute(select(VoiceProfile).order_by(VoiceProfile.created_at.desc()))
    return result.scalars().all()

async def delete_voice_profile(db: AsyncSession, profile_id: uuid.UUID):
    result = await db.execute(select(VoiceProfile).filter(VoiceProfile.id == profile_id))
    profile = result.scalars().first()
    if profile:
        await db.delete(profile)
        await db.commit()
        return True
    return False

async def get_all_sessions(db: AsyncSession):
    result = await db.execute(select(DetectionSession).order_by(DetectionSession.start_time.desc()))
    return result.scalars().all()

async def get_all_alerts(db: AsyncSession):
    result = await db.execute(select(Alert).order_by(Alert.created_at.desc()))
    return result.scalars().all()

async def create_alert(
    db: AsyncSession,
    session_id: uuid.UUID,
    severity: str,
    trigger_reason: str,
    risk_score: float
):
    alert = Alert(
        session_id=session_id,
        severity=severity,
        trigger_reason=trigger_reason,
        risk_score=risk_score
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert
