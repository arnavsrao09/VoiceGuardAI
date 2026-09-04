from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import VoiceProfile, DetectionSession, RiskTelemetry, Alert, Organization, ApiKey
import uuid

async def create_organization(db: AsyncSession, name: str, email: str, hashed_password: str):
    org = Organization(name=name, email=email, hashed_password=hashed_password)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org

async def get_organization_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(Organization).filter(Organization.email == email))
    return result.scalars().first()

async def get_organization_by_id(db: AsyncSession, org_id: uuid.UUID):
    result = await db.execute(select(Organization).filter(Organization.id == org_id))
    return result.scalars().first()

async def create_api_key(db: AsyncSession, organization_id: uuid.UUID, key_hash: str, prefix: str):
    api_key = ApiKey(organization_id=organization_id, key_hash=key_hash, prefix=prefix)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key

async def get_api_key_by_hash(db: AsyncSession, key_hash: str):
    result = await db.execute(select(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True))
    return result.scalars().first()

async def get_api_keys_for_org(db: AsyncSession, organization_id: uuid.UUID):
    result = await db.execute(select(ApiKey).filter(ApiKey.organization_id == organization_id, ApiKey.is_active == True).order_by(ApiKey.created_at.desc()))
    return result.scalars().all()

async def revoke_api_key(db: AsyncSession, key_id: uuid.UUID, organization_id: uuid.UUID):
    result = await db.execute(select(ApiKey).filter(ApiKey.id == key_id, ApiKey.organization_id == organization_id))
    key = result.scalars().first()
    if key:
        key.is_active = False
        await db.commit()
        return True
    return False

async def create_voice_profile(db: AsyncSession, organization_id: uuid.UUID, external_user_id: str, name: str, embedding: list[float], language: str = "en"):
    db_profile = VoiceProfile(
        organization_id=organization_id,
        external_user_id=external_user_id,
        name=name,
        embedding=embedding,
        language=language
    )
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return db_profile

async def get_voice_profile(db: AsyncSession, profile_id: uuid.UUID | str, organization_id: uuid.UUID = None):
    if isinstance(profile_id, str):
        try:
            profile_id = uuid.UUID(profile_id)
        except ValueError:
            return None
    query = select(VoiceProfile).filter(VoiceProfile.id == profile_id)
    if organization_id:
        query = query.filter(VoiceProfile.organization_id == organization_id)
    result = await db.execute(query)
    return result.scalars().first()

async def get_voice_profile_by_external_id(db: AsyncSession, external_user_id: str, organization_id: uuid.UUID):
    result = await db.execute(select(VoiceProfile).filter(VoiceProfile.external_user_id == external_user_id, VoiceProfile.organization_id == organization_id))
    return result.scalars().first()

async def create_detection_session(db: AsyncSession, caller_id: str, organization_id: uuid.UUID = None, api_key_id: uuid.UUID = None):
    session = DetectionSession(caller_id=caller_id, organization_id=organization_id, api_key_id=api_key_id)
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
    risk_score: float,
    organization_id: uuid.UUID = None
):
    alert = Alert(
        organization_id=organization_id,
        session_id=session_id,
        severity=severity,
        trigger_reason=trigger_reason,
        risk_score=risk_score
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert

async def get_all_voice_profiles(db: AsyncSession, organization_id: uuid.UUID = None):
    query = select(VoiceProfile).order_by(VoiceProfile.created_at.desc())
    if organization_id:
        query = query.filter(VoiceProfile.organization_id == organization_id)
    result = await db.execute(query)
    return result.scalars().all()

async def delete_voice_profile(db: AsyncSession, profile_id: uuid.UUID | str, organization_id: uuid.UUID = None):
    if isinstance(profile_id, str):
        try:
            profile_id = uuid.UUID(profile_id)
        except ValueError:
            return False
    query = select(VoiceProfile).filter(VoiceProfile.id == profile_id)
    if organization_id:
        query = query.filter(VoiceProfile.organization_id == organization_id)
    result = await db.execute(query)
    profile = result.scalars().first()
    if profile:
        await db.delete(profile)
        await db.commit()
        return True
    return False

async def get_all_sessions(db: AsyncSession, organization_id: uuid.UUID = None):
    query = select(DetectionSession).order_by(DetectionSession.start_time.desc())
    if organization_id:
        query = query.filter(DetectionSession.organization_id == organization_id)
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    # Fill in missing avg_risk_scores if needed
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

async def get_all_alerts(db: AsyncSession, organization_id: uuid.UUID = None):
    query = select(Alert).order_by(Alert.created_at.desc())
    if organization_id:
        query = query.filter(Alert.organization_id == organization_id)
    result = await db.execute(query)
    return result.scalars().all()
