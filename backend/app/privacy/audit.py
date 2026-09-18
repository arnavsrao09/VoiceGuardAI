import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import PrivacyAuditLog

async def log_privacy_event(db: AsyncSession, event_type: str, details: dict, organization_id: uuid.UUID = None):
    """
    Log a privacy-related event to the immutable audit log.
    Valid event_types: 
    - PRIVACY_MODE_CHANGED
    - DATA_PURGE_SCHEDULED
    - DATA_PURGE_COMPLETED
    - RIGHT_TO_ERASURE
    - COMPLIANCE_REPORT_EXPORTED
    - RETENTION_POLICY_UPDATED
    - CONSENT_RECORDED
    """
    audit_entry = PrivacyAuditLog(
        organization_id=organization_id,
        event_type=event_type,
        details=details,
        created_at=datetime.utcnow()
    )
    db.add(audit_entry)
    await db.commit()
    await db.refresh(audit_entry)
    return audit_entry

async def get_audit_log(db: AsyncSession, organization_id: uuid.UUID = None, limit: int = 100):
    """Retrieve recent privacy audit entries."""
    query = select(PrivacyAuditLog).order_by(PrivacyAuditLog.created_at.desc()).limit(limit)
    if organization_id:
        query = query.filter(PrivacyAuditLog.organization_id == organization_id)
    result = await db.execute(query)
    return result.scalars().all()
