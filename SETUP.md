# VoiceGuardAI — Setup & Installation Guide

This guide provides step-by-step instructions for setting up and running **VoiceGuardAI** locally, including downloading the required machine learning models and running frontend/backend servers.

---

## 📋 Prerequisites

Before getting started, make sure you have installed:
- **Python 3.11+** (or [`uv`](https://github.com/astral-sh/uv) package manager)
- **Node.js 18+** & `npm`
- **Git**
- *(Optional)* **Docker** & **Docker Compose**

---

## 🚀 Quick Start (Local Setup)

### 1. Clone the Repository

```bash
git clone https://github.com/arnavsrao09/VoiceGuardAI.git
cd VoiceGuardAI
```

---

### 2. Backend Setup

Navigate to the `backend` directory:

```bash
cd backend
```

#### Option A: Using `uv` (Recommended for speed)
```bash
# Create virtual environment and install dependencies
uv sync

# Run backend dev server
uv run uvicorn app.main:app --reload --port 8000
```

#### Option B: Using standard Python `venv`
```bash
# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend dev server
uvicorn app.main:app --reload --port 8000
```

---

### 3. Database Configuration (Cloud vs Local)

You can run the PostgreSQL database locally or use a cloud provider like **Supabase** so your whole team shares the same voice profiles.

**Option A: Cloud Postgres (Supabase) - Recommended for Teams**
1. Create a new project on [Supabase](https://supabase.com).
2. Go to your Supabase SQL Editor and enable the `pgvector` extension:
   ```sql
   create extension if not exists vector;
   ```
3. Get your connection string from Project Settings > Database.
4. Copy `.env.example` to `.env` in the `backend/` directory:
   ```bash
   cp .env.example .env
   ```
5. Update `DATABASE_URL` in `.env` to use your Supabase string, changing `postgresql://` to `postgresql+asyncpg://` to match our async driver.

**Option B: Local Postgres (Docker)**
If you prefer a local isolated database, you can start the provided containers:
```bash
docker-compose up -d postgres redis
```

---

### 4. Downloading Machine Learning Models

Model binary files (`*.onnx.data`, `*.jit`, `*.ckpt`) are excluded from Git to keep the repository lightweight.

* **Mock Mode (Default):** If no model files are present, the backend automatically runs in **Mock Mode** using deterministic outputs so you can test the frontend, WebSocket streaming, and API endpoints immediately without downloading heavy models.
* **Full ML Inference Mode:** To download and export actual pretrained models (AASIST, Silero VAD, ECAPA-TDNN, XLS-R 300M) locally:

Run the automated model downloader script inside the `backend` folder. This script will automatically pull from HuggingFace/PyTorch Hub and save the `.onnx` files to `app/ml/models/`.

```bash
# Make sure you are inside the backend directory
uv run python -m scripts.download_models
```
*(Note for Windows users: If you run into privilege errors, the script has built-in fallbacks. Do not use Admin mode unless absolutely necessary.)*

---

### 4. Frontend Setup

Open a new terminal window, navigate to the `frontend` directory, and start the Vite dev server:

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Open your browser and navigate to: **`http://localhost:5173`** (or the URL printed in terminal).

---

## 🐳 Alternative: Docker Compose Setup

If you prefer running everything in containers using Docker:

```bash
# From the root project directory
docker-compose up --build
```

Services started:
- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **PostgreSQL Database**: `localhost:5432`
- **Redis Cache**: `localhost:6379`

---

## 📁 Repository Structure Overview

```
VoiceGuardAI/
├── backend/
│   ├── app/
│   │   ├── api/             # REST & WebSocket Endpoints
│   │   ├── core/            # VAD & Audio Buffer Logic
│   │   ├── db/              # Database Models & CRUD
│   │   └── ml/              # Deepfake Detector & Prosody Analyzers
│   ├── scripts/
│   │   └── download_models.py # Model Download & ONNX Exporter
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React UI Components
│   │   ├── hooks/           # Web Audio & WebSocket Hooks
│   │   └── pages/           # Landing, Dashboard, Alerts, Settings
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── SETUP.md
```

---

## ❓ Troubleshooting & FAQs

* **Q: Do I need a GPU to run this project?**
  * **A:** No! The models are exported to ONNX format and run efficiently on CPU for real-time stream analysis.
* **Q: Why are model files missing after cloning?**
  * **A:** Model files (>1GB) are excluded from git repository limits. Run `python -m scripts.download_models` in the `backend/` directory to generate them locally.
