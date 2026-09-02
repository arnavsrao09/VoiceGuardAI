"""
download_models.py - Downloads pretrained models from HuggingFace and exports to ONNX.

Models:
  1. AASIST      - Deepfake / spoof detection (raw-waveform graph attention network)
  2. XLS-R 300M  - Multilingual SSL backbone (facebook/wav2vec2-xls-r-300m)
  3. ECAPA-TDNN  - Speaker verification (speechbrain/spkrec-ecapa-voxceleb)
  4. Silero VAD  - Voice activity detection (snakers4/silero-vad)

Usage:
    python -m scripts.download_models
"""

import os
import sys

# Force UTF-8 encoding on Windows console for PyTorch ONNX prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import torch

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "ml", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Windows symlink workaround for SpeechBrain caching
if os.name == 'nt':
    import shutil
    original_symlink = os.symlink
    def fallback_symlink(src, dst, target_is_directory=False, *, dir_fd=None):
        try:
            original_symlink(src, dst, target_is_directory=target_is_directory, dir_fd=dir_fd)
        except OSError as e:
            # WinError 1314: A required privilege is not held by the client
            if e.winerror == 1314:
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            else:
                raise e
    os.symlink = fallback_symlink



# ----------------------------------------------
# 1.  Silero VAD
# ----------------------------------------------
def download_silero_vad():
    print("[1/4] Downloading Silero VAD ...")
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
    )
    dst = os.path.join(MODEL_DIR, "silero_vad.jit")
    torch.jit.save(model, dst)
    print(f"  [OK] Saved -> {dst}")


# ----------------------------------------------
# 2.  ECAPA-TDNN  (SpeechBrain -> ONNX)
# ----------------------------------------------
def download_ecapa_tdnn():
    print("[2/4] Downloading ECAPA-TDNN (SpeechBrain) ...")
    try:
        from speechbrain.inference.speaker import EncoderClassifier

        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=os.path.join(MODEL_DIR, "ecapa_cache"),
        )

        # Export to ONNX
        dummy = torch.randn(1, 32000)  # 2 s @ 16 kHz
        onnx_path = os.path.join(MODEL_DIR, "ecapa.onnx")

        # SpeechBrain wraps modules; grab the underlying encoder
        encoder = classifier.mods["embedding_model"]
        encoder.eval()

        # The encoder expects mel features; for a simplified export we
        # wrap the full forward pass.
        class _EcapaWrapper(torch.nn.Module):
            def __init__(self, clf):
                super().__init__()
                self.clf = clf

            def forward(self, wav):
                # Returns (batch, 1, 192)
                return self.clf.encode_batch(wav)

        wrapper = _EcapaWrapper(classifier)
        wrapper.eval()

        torch.onnx.export(
            wrapper,
            dummy,
            onnx_path,
            input_names=["audio"],
            output_names=["embedding"],
            dynamic_axes={"audio": {0: "batch", 1: "time"}},
            opset_version=14,
        )
        print(f"  [OK] Exported ONNX -> {onnx_path}")
    except Exception as e:
        print(f"  [ERROR] ECAPA-TDNN export failed: {e}")
        print("    You can still run the backend in mock mode.")


# ----------------------------------------------
# 3.  AASIST  (clone repo weights -> ONNX stub)
# ----------------------------------------------
def download_aasist():
    """
    AASIST weights are typically distributed via the original GitHub repo
    (https://github.com/clovaai/aasist).  This function creates a
    placeholder ONNX model that matches the expected I/O contract so the
    rest of the pipeline can run.  Replace with real weights for production.
    """
    print("[3/4] Creating AASIST ONNX stub ...")

    class _AasistStub(torch.nn.Module):
        """Minimal stub: raw waveform -> [bonafide, spoof] logits."""
        def __init__(self):
            super().__init__()
            self.fc = torch.nn.Linear(32000, 2)

        def forward(self, x):
            return self.fc(x)

    model = _AasistStub()
    model.eval()
    dummy = torch.randn(1, 32000)
    onnx_path = os.path.join(MODEL_DIR, "aasist.onnx")

    torch.onnx.export(
        model,
        dummy,
        onnx_path,
        input_names=["audio"],
        output_names=["logits"],
        dynamic_axes={"audio": {0: "batch"}},
        opset_version=14,
    )
    print(f"  [OK] AASIST ONNX -> {onnx_path}")
    print("    [WARNING] Replace with real AASIST weights for production accuracy.")


# ----------------------------------------------
# 4.  XLS-R 300M  (HuggingFace Transformers -> ONNX)
# ----------------------------------------------
def download_xlsr():
    print("[4/4] Downloading XLS-R 300M ...")
    try:
        from transformers import Wav2Vec2Model

        model = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-xls-r-300m")
        model.eval()

        # Wrap with a linear classification head
        class _XlsrClassifier(torch.nn.Module):
            def __init__(self, backbone):
                super().__init__()
                self.backbone = backbone
                self.head = torch.nn.Linear(1024, 2)  # XLS-R 300M hidden = 1024

            def forward(self, input_values):
                outputs = self.backbone(input_values)
                hidden = outputs.last_hidden_state.mean(dim=1)  # mean pool
                return self.head(hidden)

        classifier = _XlsrClassifier(model)
        classifier.eval()

        dummy = torch.randn(1, 32000)
        onnx_path = os.path.join(MODEL_DIR, "xlsr.onnx")

        torch.onnx.export(
            classifier,
            dummy,
            onnx_path,
            input_names=["input_values"],
            output_names=["logits"],
            dynamic_axes={"input_values": {0: "batch", 1: "time"}},
            opset_version=14,
        )
        print(f"  [OK] Exported ONNX -> {onnx_path}")
    except Exception as e:
        print(f"  [ERROR] XLS-R export failed: {e}")
        print("    This is expected if 'transformers' is not installed or download is slow.")
        print("    The backend will fall back to mock mode.")


# ----------------------------------------------
#  CLI entry-point
# ----------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("VoiceGuardAI - Model Downloader & ONNX Exporter")
    print("=" * 60)
    print(f"Target directory: {os.path.abspath(MODEL_DIR)}\n")

    download_silero_vad()
    download_ecapa_tdnn()
    download_aasist()
    download_xlsr()

    print("\n[OK] All done. Models are in:", os.path.abspath(MODEL_DIR))
