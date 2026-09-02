import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_models():
    base_dir = Path(__file__).parent.parent
    models_dir = base_dir / "models"
    
    logger.info("Checking ML models...")
    
    ecapa = models_dir / "ecapa"
    aasist = models_dir / "aasist"
    
    if os.path.exists(ecapa) and len(os.listdir(ecapa)) > 0:
        logger.info("✅ ECAPA-TDNN found.")
    else:
        logger.warning("❌ ECAPA-TDNN missing. Run download_models.py")
        
    if os.path.exists(aasist) and any(f.endswith('.pth') or f.endswith('.onnx') for f in os.listdir(aasist)):
        logger.info("✅ AASIST model found.")
    else:
        logger.warning("❌ AASIST model missing. Please place weights in models/aasist or enable MOCK_ML.")

if __name__ == "__main__":
    check_models()
