# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
React (Vite) + TailwindCSS on the frontend.
FastAPI (Python 3.11+) on the backend with PostgreSQL (pgvector).
Deployed via Docker Compose.

## Users
Financial institutions, enterprises, and government agencies seeking to detect and prevent fraud caused by AI voice cloning and synthetic speech.

## Product Purpose
An end-to-end real-time framework that analyzes live voice streams (e.g., phone calls), computes dynamic impersonation risk scores, and delivers actionable alerts. Success means detecting deepfakes in under 400ms with high accuracy (EER < 5%) while preserving privacy.

## Positioning
Purpose-built for voice cloning threats using a multi-layer ensemble (AASIST graph attention, Wav2Vec2 XLS-R, ECAPA-TDNN speaker verification, and prosody forensics) rather than generic audio classification. Processes live binary PCM streams over WebSocket.

## Operating Context
Live call monitoring dashboards and batch analysis workflows. Used by security operators, fraud analysts, and automated response systems (e.g., auto-holding transactions on high risk).

## Capabilities and Constraints
- Must operate in real-time (sub-400ms latency).
- Multilingual support prioritizing Indian languages (Hindi, Tamil, Telugu, Bengali, etc.) via XLS-R backbone.
- Privacy-preserving: Zero raw audio retention; features-only logging.
- Deployed as a Dockerized stack (hackathon prototype with path to production).

## Evidence on Hand
- ASVspoof 2019/2021, WaveFake, IndicVoices datasets are used for training/eval.
- No real user testimonials yet (hackathon prototype).
- Synthesized and real demo audio required to prove efficacy.

## Product Principles
1. **Speed is Security**: Detection must happen before the transaction completes.
2. **Privacy by Design**: Never store raw audio; discard after feature extraction.
3. **Multi-Layer Defense**: Rely on an ensemble of acoustic, linguistic, and speaker identity signals, never just one model.

## Accessibility & Inclusion
Must support multiple languages and dialects, particularly Indian regional languages and code-switching (Hinglish/Tanglish).
