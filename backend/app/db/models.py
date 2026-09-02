import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone

from app.db.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class VoiceProfile(Base):
    __tablename__ = "voice_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    language = Column(String, nullable=True)
    embedding = Column(Vector(192), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class DetectionSession(Base):
    __tablename__ = "detection_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caller_id = Column(UUID(as_uuid=True), nullable=True) # can link to user or voice profile
    start_time = Column(DateTime(timezone=True), default=utcnow)
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="active") # active, completed, failed
    avg_risk_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    
    telemetry = relationship("RiskTelemetry", back_populates="session", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="session", cascade="all, delete-orphan")

class RiskTelemetry(Base):
    __tablename__ = "risk_telemetry"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("detection_sessions.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    chunk_index = Column(Integer, nullable=False)
    risk_score = Column(Float, nullable=False)
    deepfake_probability = Column(Float, nullable=False)
    speaker_similarity = Column(Float, nullable=True)
    prosody_score = Column(Float, nullable=False)
    context_score = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    anomaly_flags = Column(JSONB, nullable=True)
    
    session = relationship("DetectionSession", back_populates="telemetry")

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("detection_sessions.id", ondelete="CASCADE"), nullable=False)
    severity = Column(String, nullable=False) # HIGH, CRITICAL
    trigger_reason = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    action_taken = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    
    session = relationship("DetectionSession", back_populates="alerts")

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String, nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
