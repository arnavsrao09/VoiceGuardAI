import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def verify_environment():
    if sys.version_info < (3, 11):
        logger.error("Python 3.11+ is required.")
        sys.exit(1)
        
    try:
        import torch
        import speechbrain
        import torchaudio
    except ImportError as e:
        logger.error(f"Missing dependency: {e}. Please run `uv sync` first.")
        sys.exit(1)

def download_models():
    base_dir = Path(__file__).parent.parent
    models_dir = base_dir / "models"
    aasist_dir = models_dir / "aasist"
    ecapa_dir = models_dir / "ecapa"
    
    os.makedirs(aasist_dir, exist_ok=True)
    os.makedirs(ecapa_dir, exist_ok=True)

    logger.info("Initializing model downloads...")
    
    # 1. Silero VAD (Loaded via torch hub)
    logger.info("Downloading Silero VAD (via torch.hub)...")
    import torch
    torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False, trust_repo=True)
    
    # 2. ECAPA-TDNN (Loaded via speechbrain)
    logger.info("Downloading ECAPA-TDNN (via speechbrain)...")
    from speechbrain.inference.speaker import EncoderClassifier
    EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(ecapa_dir)
    )
    
    # 3. AASIST
    logger.info("AASIST model weights need to be downloaded from the official repository:")
    logger.info("https://github.com/clovaai/aasist")
    logger.info("For this hackathon prototype, if AASIST is not present in models/aasist, the backend will use a mock mode or you can set MOCK_ML=true in .env")
    
    # Creating a dummy file to satisfy directory existence if needed
    (aasist_dir / ".gitkeep").touch(exist_ok=True)
    
    logger.info("Model download step complete.")

if __name__ == "__main__":
    verify_environment()
    download_models()
    print("\nInstructions:")
    print("1. Models are stored in the 'models' directory.")
    print("2. Make sure to set MOCK_ML=false if you want to use real models.")
    print("3. Run 'uv run uvicorn app.main:app --reload' to start the server.")
