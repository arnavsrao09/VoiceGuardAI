"""
Ensemble risk scoring and threat decision engine with EMA smoothing and debounced alerts.

Decouples deepfake detection from speaker verification into two distinct branches:
1. Deepfake/Spoof Branch: AASIST + XLS-R + supporting prosody forensics -> calibrated spoof score.
2. Speaker Verification Branch: ECAPA-TDNN cosine similarity against reference profile.

Threat Decision Matrix:
- Q1: GENUINE_ENROLLED_SPEAKER     (High similarity, Low spoof) -> ALLOW / Verified
- Q2: GENUINE_DIFFERENT_SPEAKER    (Low similarity, Low spoof)  -> IDENTITY_MISMATCH / Deny Biometrics
- Q3: VOICE_CLONE_IMPERSONATION    (High similarity, High spoof)-> CRITICAL / Terminate Call
- Q4: SYNTHETIC_UNKNOWN_SPEAKER    (Low similarity, High spoof) -> HIGH_RISK / Challenge Caller
"""

from __future__ import annotations

from dataclasses import dataclass
from app.config import settings


@dataclass
class _AlertState:
    """Internal bookkeeping for alert debouncing."""
    consecutive_high: int = 0
    alert_fired: bool = False
    last_alert_reason: str | None = None


class ThreatCategory:
    GENUINE_ENROLLED = "GENUINE_ENROLLED_SPEAKER"
    GENUINE_DIFFERENT = "GENUINE_DIFFERENT_SPEAKER"
    VOICE_CLONE_IMPERSONATION = "VOICE_CLONE_IMPERSONATION"
    SYNTHETIC_UNKNOWN = "SYNTHETIC_UNKNOWN_SPEAKER"
    GENUINE_UNENROLLED = "GENUINE_SPEAKER"
    SYNTHETIC_UNENROLLED = "SYNTHETIC_SPEAKER"


class ProtectionAction:
    ALLOW = "ALLOW"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    CHALLENGE_CALLER = "CHALLENGE_CALLER"
    TERMINATE_SESSION = "TERMINATE_SESSION"
    MONITOR = "MONITOR"
    FLAG_FRAUD = "FLAG_FRAUD"


class RiskScorer:
    """Decoupled Threat Decision and Risk Scoring Engine."""

    LEVEL_LOW = "LOW"
    LEVEL_MEDIUM = "MEDIUM"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"

    def __init__(
        self,
        ema_alpha: float = 0.35,
        alert_consecutive_threshold: int = 1,
        speaker_threshold: float | None = None,
        deepfake_threshold: float | None = None,
    ):
        self.ema_alpha = ema_alpha
        self.alert_consecutive_threshold = alert_consecutive_threshold
        self.speaker_threshold = (
            speaker_threshold if speaker_threshold is not None
            else settings.speaker_verification_threshold
        )
        self.deepfake_threshold = (
            deepfake_threshold if deepfake_threshold is not None
            else settings.deepfake_threshold
        )

        self._current_ema: float = 0.0
        self._chunk_count: int = 0
        self._alert = _AlertState()

    def compute_score(
        self,
        deepfake_prob: float,
        speaker_match: float,
        prosody_anomaly: float = 0.0,
        speaker_drift: float = 0.0,
        context_risk: float = 0.0,
        deepfake_confidence: float = 1.0,
        has_enrollment: bool = False,
    ) -> dict:
        """Evaluate decoupled branches and categorize the threat."""
        self._chunk_count += 1

        # ── Strict NaN / Inf input sanitation ─────────────────────────
        import numpy as np

        if speaker_match is None or np.isnan(speaker_match) or np.isinf(speaker_match):
            speaker_match = 0.0
        else:
            speaker_match = float(np.clip(speaker_match, -1.0, 1.0))

        if deepfake_prob is None or np.isnan(deepfake_prob) or np.isinf(deepfake_prob):
            deepfake_prob = 0.20
        else:
            deepfake_prob = float(np.clip(deepfake_prob, 0.0, 1.0))

        if prosody_anomaly is None or np.isnan(prosody_anomaly) or np.isinf(prosody_anomaly):
            prosody_anomaly = 0.0
        else:
            prosody_anomaly = float(np.clip(prosody_anomaly, 0.0, 1.0))

        if speaker_drift is None or np.isnan(speaker_drift) or np.isinf(speaker_drift):
            speaker_drift = 0.0
        else:
            speaker_drift = float(np.clip(speaker_drift, 0.0, 1.0))

        is_synthetic = deepfake_prob >= self.deepfake_threshold
        is_same_speaker: bool | None = None

        if has_enrollment:
            is_same_speaker = speaker_match >= self.speaker_threshold

            if is_same_speaker and not is_synthetic:
                # ── Q1: Legitimate Enrolled User ──────────────────────
                threat_category = ThreatCategory.GENUINE_ENROLLED
                level = self.LEVEL_LOW
                raw_score = deepfake_prob * 0.40  # stays safely in [0.0, 0.20]
                action = ProtectionAction.ALLOW
                reason = "Legitimate enrolled speaker with natural human voice."
                should_alert = False

            elif not is_same_speaker and not is_synthetic:
                # ── Q2: Genuine Human, Different Identity ─────────────
                threat_category = ThreatCategory.GENUINE_DIFFERENT
                level = self.LEVEL_MEDIUM
                # Distinguish identity failure from deepfake:
                # Fixed medium level (0.45 - 0.55), explicit mismatch tag
                raw_score = 0.45 + (1.0 - max(0.0, speaker_match)) * 0.10
                action = ProtectionAction.IDENTITY_MISMATCH
                reason = (
                    f"Identity mismatch: Human voice detected, but does not match "
                    f"enrolled profile (similarity: {speaker_match:.2f} < {self.speaker_threshold:.2f})."
                )
                should_alert = True

            elif is_same_speaker and is_synthetic:
                # ── Q3: Voice Cloning Impersonation Attack ─────────────
                threat_category = ThreatCategory.VOICE_CLONE_IMPERSONATION
                level = self.LEVEL_CRITICAL
                raw_score = max(0.88, deepfake_prob)
                action = ProtectionAction.TERMINATE_SESSION
                reason = (
                    f"CRITICAL: AI voice clone detected impersonating enrolled user identity "
                    f"(similarity: {speaker_match:.2f}, spoof: {deepfake_prob:.2f})!"
                )
                should_alert = True

            else:
                # ── Q4: Synthetic / Generic Spoofed Audio ──────────────
                threat_category = ThreatCategory.SYNTHETIC_UNKNOWN
                level = self.LEVEL_HIGH
                raw_score = max(0.70, deepfake_prob)
                action = ProtectionAction.CHALLENGE_CALLER
                reason = (
                    f"Synthetic audio detected from unknown/mismatched voice "
                    f"(spoof: {deepfake_prob:.2f})."
                )
                should_alert = True

        else:
            # ── Unenrolled General Monitoring ─────────────────────────
            is_same_speaker = None
            if not is_synthetic:
                threat_category = ThreatCategory.GENUINE_UNENROLLED
                level = self.LEVEL_LOW
                raw_score = deepfake_prob * 0.50
                action = ProtectionAction.MONITOR
                reason = "Natural human voice detected."
                should_alert = False
            else:
                threat_category = ThreatCategory.SYNTHETIC_UNENROLLED
                level = self.LEVEL_CRITICAL if deepfake_prob >= 0.80 else self.LEVEL_HIGH
                raw_score = deepfake_prob
                action = ProtectionAction.FLAG_FRAUD
                reason = f"AI-generated / synthetic voice detected (spoof: {deepfake_prob:.2f})."
                should_alert = True

        # Mid-call speaker drift override
        if speaker_drift >= 0.40:
            if level in (self.LEVEL_LOW, self.LEVEL_MEDIUM):
                level = self.LEVEL_HIGH
                raw_score = max(raw_score, 0.72)
                reason += f" | Mid-call speaker switch detected (drift: {speaker_drift:.2f})"
                should_alert = True

        if np.isnan(raw_score) or np.isinf(raw_score):
            raw_score = 0.0
        raw_score = max(0.0, min(1.0, raw_score))

        # ── EMA Smoothing ─────────────────────────────────────────────
        if self._chunk_count == 1 or np.isnan(self._current_ema):
            self._current_ema = raw_score
        else:
            self._current_ema = (
                self.ema_alpha * raw_score
                + (1 - self.ema_alpha) * self._current_ema
            )
        if np.isnan(self._current_ema) or np.isinf(self._current_ema):
            self._current_ema = raw_score

        # Debounce alert for sustained levels if necessary
        alert_fired, alert_reason = self._update_alert(
            should_alert=should_alert,
            level=level,
            reason=reason,
        )

        return {
            "score": round(self._current_ema, 4),
            "raw_score": round(raw_score, 4),
            "level": level,
            "threat_category": threat_category,
            "action_recommendation": action,
            "should_alert": alert_fired,
            "alert_reason": alert_reason,
            "has_enrollment": has_enrollment,
            "is_same_speaker": is_same_speaker,
            "speaker_similarity": round(speaker_match, 4) if has_enrollment else None,
            "deepfake_score": round(deepfake_prob, 4),
            "chunk_index": self._chunk_count,
            "raw_components": {
                "deepfake": round(deepfake_prob, 4),
                "speaker": round(speaker_match, 4) if has_enrollment else 1.0,
                "speaker_drift": round(speaker_drift, 4),
                "prosody": round(prosody_anomaly, 4),
                "context": round(context_risk, 4),
            },
        }

    def reset(self):
        """Reset scoring state (call at session start)."""
        self._current_ema = 0.0
        self._chunk_count = 0
        self._alert = _AlertState()

    def _update_alert(
        self,
        should_alert: bool,
        level: str,
        reason: str,
    ) -> tuple[bool, str | None]:
        """Debounced alert generation."""
        if should_alert and level in (self.LEVEL_MEDIUM, self.LEVEL_HIGH, self.LEVEL_CRITICAL):
            self._alert.consecutive_high += 1
        else:
            self._alert.consecutive_high = 0
            self._alert.alert_fired = False
            self._alert.last_alert_reason = None
            return False, None

        if self._alert.consecutive_high >= self.alert_consecutive_threshold:
            self._alert.alert_fired = True
            self._alert.last_alert_reason = reason
            self._alert.consecutive_high = 0
            return True, reason

        return False, None
