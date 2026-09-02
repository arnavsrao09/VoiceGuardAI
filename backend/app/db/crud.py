from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import VoiceProfile, DetectionSession, RiskTelemetry, Alert
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

async def get_voice_profile(db: AsyncSession, profile_id: uuid.UUID | str):
    if isinstance(profile_id, str):
        try:
            profile_id = uuid.UUID(profile_id)
        except ValueError:
            return None
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

async def create_alert(
    db: AsyncSession,
    session_id: uuid.UUID,
    severity: str,
    trigger_reason: str,
    risk_score: float
):
    """Create and persist a detection alert."""
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

async def get_all_voice_profiles(db: AsyncSession):
    result = await db.execute(select(VoiceProfile).order_by(VoiceProfile.created_at.desc()))
    return result.scalars().all()

async def delete_voice_profile(db: AsyncSession, profile_id: uuid.UUID | str):
    if isinstance(profile_id, str):
        try:
            profile_id = uuid.UUID(profile_id)
        except ValueError:
            return False
    result = await db.execute(select(VoiceProfile).filter(VoiceProfile.id == profile_id))
    profile = result.scalars().first()
    if profile:
        await db.delete(profile)
        await db.commit()
        return True
    return False

async def get_all_sessions(db: AsyncSession):
    result = await db.execute(select(DetectionSession).order_by(DetectionSession.start_time.desc()))
    sessions = result.scalars().all()
    for s in sessions:
        if s.avg_risk_score is None:
            alert_res = await db.execute(
                select(Alert.risk_score)
                .where(Alert.session_id == s.session_id)
                .order_by(Alert.risk_score.desc())
            )
            top_alert = alert_res.scalars().first()
            if top_alert is not None:
                s.avg_risk_score = round(float(top_alert), 3)
    return sessions

async def get_all_alerts(db: AsyncSession):
    result = await db.execute(select(Alert).order_by(Alert.created_at.desc()))
    return result.scalars().all()
