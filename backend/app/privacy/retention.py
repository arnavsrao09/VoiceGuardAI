import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update, func
from app.db.models import RetentionConfig, DetectionSession, RiskTelemetry, VoiceProfile, Alert
from app.config import settings
from .audit import log_privacy_event

@dataclass
class RetentionPolicy:
    session_ttl_days: float
    telemetry_ttl_days: float
    embedding_ttl_days: float
    alert_ttl_days: float

class DataRetentionManager:
    @classmethod
    async def get_retention_config(cls, db: AsyncSession, organization_id: uuid.UUID) -> RetentionConfig:
        result = await db.execute(select(RetentionConfig).filter(RetentionConfig.organization_id == organization_id))
        config = result.scalars().first()
        if not config:
            config = RetentionConfig(
                organization_id=organization_id,
                session_ttl_days=settings.default_session_ttl_days,
                telemetry_ttl_days=settings.default_telemetry_ttl_days,
                embedding_ttl_days=settings.default_embedding_ttl_days,
                alert_ttl_days=settings.default_alert_ttl_days,
                inference_mode=settings.default_inference_mode
            )
            db.add(config)
            await db.commit()
            await db.refresh(config)
        return config

    @classmethod
    async def update_retention_config(cls, db: AsyncSession, organization_id: uuid.UUID, **kwargs):
        config = await cls.get_retention_config(db, organization_id)
        
        old_values = {
            "session_ttl_days": config.session_ttl_days,
            "telemetry_ttl_days": config.telemetry_ttl_days,
            "embedding_ttl_days": config.embedding_ttl_days,
            "alert_ttl_days": config.alert_ttl_days,
            "inference_mode": config.inference_mode
        }

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        await db.commit()
        await db.refresh(config)

        # Log audit event
        await log_privacy_event(
            db, 
            "RETENTION_POLICY_UPDATED", 
            {"old": old_values, "new": kwargs}, 
            organization_id
        )
        return config

    @classmethod
    async def purge_expired_sessions(cls, db: AsyncSession, org_id: uuid.UUID, ttl_days: float) -> int:
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        stmt = delete(DetectionSession).where(
            DetectionSession.organization_id == org_id,
            DetectionSession.start_time < cutoff
        )
        result = await db.execute(stmt)
        return result.rowcount

    @classmethod
    async def purge_expired_telemetry(cls, db: AsyncSession, org_id: uuid.UUID, ttl_days: float) -> int:
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        # We join on DetectionSession to get org_id
        # For sqlite compatibility without complicated joins in delete, we find session IDs first
        sess_stmt = select(DetectionSession.session_id).where(DetectionSession.organization_id == org_id)
        sess_res = await db.execute(sess_stmt)
        session_ids = [row[0] for row in sess_res.fetchall()]

        if not session_ids:
            return 0

        stmt = delete(RiskTelemetry).where(
            RiskTelemetry.session_id.in_(session_ids),
            RiskTelemetry.timestamp < cutoff
        )
        result = await db.execute(stmt)
        return result.rowcount

    @classmethod
    async def purge_expired_embeddings(cls, db: AsyncSession, org_id: uuid.UUID, ttl_days: float) -> int:
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        # Nullify embeddings instead of deleting profile to preserve metadata history
        stmt = update(VoiceProfile).where(
            VoiceProfile.organization_id == org_id,
            VoiceProfile.created_at < cutoff,
            VoiceProfile.embedding.isnot(None)
        ).values(embedding=None)
        result = await db.execute(stmt)
        return result.rowcount

    @classmethod
    async def purge_expired_alerts(cls, db: AsyncSession, org_id: uuid.UUID, ttl_days: float) -> int:
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        stmt = delete(Alert).where(
            Alert.organization_id == org_id,
            Alert.created_at < cutoff
        )
        result = await db.execute(stmt)
        return result.rowcount

    @classmethod
    async def run_scheduled_purge(cls, db: AsyncSession):
        # Fetch all configs
        result = await db.execute(select(RetentionConfig))
        configs = result.scalars().all()
        
        total_purged = {"sessions": 0, "telemetry": 0, "embeddings": 0, "alerts": 0}
        
        for config in configs:
            org_id = config.organization_id
            if not org_id:
                continue

            s_count = await cls.purge_expired_sessions(db, org_id, config.session_ttl_days)
            t_count = await cls.purge_expired_telemetry(db, org_id, config.telemetry_ttl_days)
            e_count = await cls.purge_expired_embeddings(db, org_id, config.embedding_ttl_days)
            a_count = await cls.purge_expired_alerts(db, org_id, config.alert_ttl_days)

            total_purged["sessions"] += s_count
            total_purged["telemetry"] += t_count
            total_purged["embeddings"] += e_count
            total_purged["alerts"] += a_count
            
            if s_count > 0 or t_count > 0 or e_count > 0 or a_count > 0:
                await log_privacy_event(
                    db,
                    "DATA_PURGE_COMPLETED",
                    {
                        "purged": {
                            "sessions": s_count,
                            "telemetry": t_count,
                            "embeddings_nullified": e_count,
                            "alerts": a_count
                        },
                        "trigger": "scheduled_background_job"
                    },
                    org_id
                )
        
        await db.commit()
        return total_purged

    @classmethod
    async def erase_organization_data(cls, db: AsyncSession, organization_id: uuid.UUID):
        # Find all sessions first
        sess_stmt = select(DetectionSession.session_id).where(DetectionSession.organization_id == organization_id)
        sess_res = await db.execute(sess_stmt)
        session_ids = [row[0] for row in sess_res.fetchall()]

        # Delete telemetry
        if session_ids:
            await db.execute(delete(RiskTelemetry).where(RiskTelemetry.session_id.in_(session_ids)))

        # Delete alerts
        await db.execute(delete(Alert).where(Alert.organization_id == organization_id))

        # Delete sessions
        await db.execute(delete(DetectionSession).where(DetectionSession.organization_id == organization_id))

        # Delete voice profiles
        await db.execute(delete(VoiceProfile).where(VoiceProfile.organization_id == organization_id))

        # We keep the config and audit log to prove erasure occurred
        await log_privacy_event(
            db,
            "RIGHT_TO_ERASURE",
            {"status": "completed", "details": "All sessions, telemetry, profiles, and alerts deleted."},
            organization_id
        )
        
        await db.commit()
        return True

    @classmethod
    async def get_data_inventory(cls, db: AsyncSession, organization_id: uuid.UUID) -> dict:
        # Sessions
        s_res = await db.execute(select(func.count(DetectionSession.session_id)).where(DetectionSession.organization_id == organization_id))
        sessions_count = s_res.scalar() or 0

        # Profiles
        p_res = await db.execute(select(func.count(VoiceProfile.id)).where(VoiceProfile.organization_id == organization_id))
        profiles_count = p_res.scalar() or 0

        # Alerts
        a_res = await db.execute(select(func.count(Alert.id)).where(Alert.organization_id == organization_id))
        alerts_count = a_res.scalar() or 0

        # Telemetry
        sess_stmt = select(DetectionSession.session_id).where(DetectionSession.organization_id == organization_id)
        sess_res = await db.execute(sess_stmt)
        session_ids = [row[0] for row in sess_res.fetchall()]

        telemetry_count = 0
        if session_ids:
            t_res = await db.execute(select(func.count(RiskTelemetry.id)).where(RiskTelemetry.session_id.in_(session_ids)))
            telemetry_count = t_res.scalar() or 0

        return {
            "sessions": sessions_count,
            "profiles": profiles_count,
            "alerts": alerts_count,
            "telemetry": telemetry_count
        }
