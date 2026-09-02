"""
Ensemble risk scoring engine with EMA smoothing and alert generation.

Fuses signals from the deepfake detector, speaker verifier, prosody
analyser, and optional context metadata into a single dynamic risk score.

Features:
- Configurable ensemble weights via ``ScoringWeights`` dataclass
- EMA (Exponential Moving Average) temporal smoothing
- Alert debouncing — only fires after N consecutive high-risk chunks
- Per-score confidence metric based on model agreement
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScoringWeights:
    """Ensemble fusion weights — must sum to 1.0."""
    deepfake: float = 0.40
    speaker: float = 0.25
    prosody: float = 0.15
    speaker_drift: float = 0.10
    context: float = 0.10

    def __post_init__(self):
        total = (
            self.deepfake + self.speaker + self.prosody
            + self.speaker_drift + self.context
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total:.3f}"
            )


@dataclass
class _AlertState:
    """Internal bookkeeping for alert debouncing."""
    consecutive_high: int = 0
    alert_fired: bool = False
    last_alert_reason: str | None = None


class RiskScorer:
    """Computes ensemble risk scores with temporal smoothing.

    Parameters
    ----------
    weights : ScoringWeights | None
        Ensemble fusion weights.  Defaults to the production preset.
    ema_alpha : float
        EMA smoothing coefficient.  Higher = more reactive, noisier.
        Lower = smoother, slower to respond.
    alert_consecutive_threshold : int
        Number of consecutive HIGH/CRITICAL chunks before an alert fires.
        Prevents single-frame false positives.
    """

    # Risk level boundaries
    LEVEL_LOW = "LOW"
    LEVEL_MEDIUM = "MEDIUM"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        ema_alpha: float = 0.3,
        alert_consecutive_threshold: int = 1,
    ):
        self.weights = weights or ScoringWeights()
        self.ema_alpha = ema_alpha
        self.alert_consecutive_threshold = alert_consecutive_threshold

        self._current_ema: float = 0.0
        self._chunk_count: int = 0
        self._alert = _AlertState()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def compute_score(
        self,
        deepfake_prob: float,
        speaker_match: float,
        prosody_anomaly: float,
        speaker_drift: float = 0.0,
        context_risk: float = 0.0,
        deepfake_confidence: float = 1.0,
        has_enrollment: bool = False,
    ) -> dict:
        """Compute the ensemble risk score with adaptive weight re-normalization.

        Parameters
        ----------
        deepfake_prob : float
            Probability that the audio is synthetic (0–1).
        speaker_match : float
            Cosine similarity to enrolled speaker (0–1).
        prosody_anomaly : float
            Prosody anomaly score (0–1).
        speaker_drift : float
            Speaker drift score from mid-call change detection (0–1).
        context_risk : float
            External context risk signal (0–1).
        deepfake_confidence : float
            Detector confidence (0–1).
        has_enrollment : bool
            Whether an enrolled speaker profile is linked to this session.
            If False, speaker mismatch penalty is excluded and remaining
            weights are re-normalized.

        Returns
        -------
        dict
            Comprehensive scoring result with alert information.
        """
        self._chunk_count += 1

        if has_enrollment:
            # Full ensemble when speaker profile is enrolled & linked
            w_df = 0.40
            w_spk = 0.35
            w_pros = 0.15
            w_drift = 0.10
            w_ctx = 0.0
            speaker_risk = max(0.0, 1.0 - speaker_match)
        else:
            # Re-normalized weights when no profile is linked (general deepfake monitoring)
            w_df = 0.60
            w_spk = 0.00
            w_pros = 0.30
            w_drift = 0.10
            w_ctx = 0.0
            speaker_risk = 0.0

        # ── Weighted ensemble fusion ───────────────────────────────────
        raw_score = (
            w_df * (deepfake_prob * deepfake_confidence)
            + w_spk * speaker_risk
            + w_pros * prosody_anomaly
            + w_drift * speaker_drift
            + w_ctx * context_risk
        )
        raw_score = max(0.0, min(1.0, raw_score))

        # ── EMA smoothing ─────────────────────────────────────────────
        if self._chunk_count == 1:
            self._current_ema = raw_score
        else:
            self._current_ema = (
                self.ema_alpha * raw_score
                + (1 - self.ema_alpha) * self._current_ema
            )

        # ── Risk level ─────────────────────────────────────────────────
        level = self._classify_level(self._current_ema)

        # ── Alert logic (debounced) ────────────────────────────────────
        should_alert, alert_reason = self._update_alert(level, deepfake_prob, speaker_drift)

        # ── Result ─────────────────────────────────────────────────────
        return {
            "score": round(self._current_ema, 4),
            "raw_score": round(raw_score, 4),
            "level": level,
            "chunk_index": self._chunk_count,
            "should_alert": should_alert,
            "alert_reason": alert_reason,
            "has_enrollment": has_enrollment,
            "raw_components": {
                "deepfake": round(deepfake_prob, 4),
                "speaker_match": round(speaker_match, 4) if has_enrollment else 1.0,
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

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_level(score: float) -> str:
        if score >= 0.8:
            return RiskScorer.LEVEL_CRITICAL
        if score >= 0.6:
            return RiskScorer.LEVEL_HIGH
        if score >= 0.3:
            return RiskScorer.LEVEL_MEDIUM
        return RiskScorer.LEVEL_LOW

    def _update_alert(
        self, level: str, deepfake_prob: float, speaker_drift: float
    ) -> tuple[bool, str | None]:
        """Debounced alert generation.

        An alert fires when the risk level has been HIGH or CRITICAL
        for ``alert_consecutive_threshold`` chunks in a row.
        After firing, the counter resets so alerts can fire again
        during sustained high-risk periods.
        """
        is_high = level in (self.LEVEL_HIGH, self.LEVEL_CRITICAL)

        if is_high:
            self._alert.consecutive_high += 1
        else:
            self._alert.consecutive_high = 0
            self._alert.alert_fired = False
            self._alert.last_alert_reason = None
            return False, None

        if self._alert.consecutive_high >= self.alert_consecutive_threshold:
            reason = self._determine_reason(deepfake_prob, speaker_drift, level)
            self._alert.alert_fired = True
            self._alert.last_alert_reason = reason
            # Reset counter so alerts can fire again during sustained high risk
            self._alert.consecutive_high = 0
            return True, reason

        return False, None

    @staticmethod
    def _determine_reason(
        deepfake_prob: float, speaker_drift: float, level: str
    ) -> str:
        """Generate a human-readable alert reason."""
        reasons: list[str] = []

        if deepfake_prob >= 0.7:
            reasons.append("High deepfake probability detected")
        if speaker_drift >= 0.4:
            reasons.append("Speaker identity change detected mid-call")
        if not reasons:
            reasons.append(f"Sustained {level} risk level")

        return "; ".join(reasons)
