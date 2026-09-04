from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey, Uuid, TypeDecorator, Boolean
import uuid
from datetime import datetime
from app.config import settings
from sqlalchemy.orm import relationship

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

class EmbeddingType(TypeDecorator):
    """Cross-dialect Embedding type (pgvector(192) on Postgres, JSON array on SQLite)."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and HAS_PGVECTOR:
            return dialect.type_descriptor(Vector(192))
        return dialect.type_descriptor(JSON)

from .database import Base

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id"))
    key_hash = Column(String, unique=True, index=True)
    prefix = Column(String)  # First few chars of the key for display
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VoiceProfile(Base):
    __tablename__ = "voice_profiles"
    
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id"))
    external_user_id = Column(String, index=True)
    name = Column(String)
    embedding = Column(EmbeddingType) # 192-dim ECAPA-TDNN embedding
    language = Column(String, default="en")
    created_at = Column(DateTime, default=datetime.utcnow)

class DetectionSession(Base):
    __tablename__ = "detection_sessions"
    
    session_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    api_key_id = Column(Uuid(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    caller_id = Column(String)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    avg_risk_score = Column(Float, nullable=True)
    status = Column(String, default="active")

class RiskTelemetry(Base):
    __tablename__ = "risk_telemetry"
    
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(Uuid(as_uuid=True), ForeignKey("detection_sessions.session_id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    chunk_index = Column(Float)
    risk_score = Column(Float)
    deepfake_prob = Column(Float)
    speaker_sim = Column(Float, nullable=True)
    prosody_score = Column(Float, nullable=True)
    anomaly_flags = Column(JSON, default=dict)

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    session_id = Column(Uuid(as_uuid=True), ForeignKey("detection_sessions.session_id"))
    severity = Column(String) # LOW, MEDIUM, HIGH, CRITICAL
    trigger_reason = Column(String)
    risk_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    action_taken = Column(String, nullable=True)
