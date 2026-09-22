import os
import urllib.request
import sys

def download_progress(count, block_size, total_size):
    percent = int(count * block_size * 100 / total_size)
    if percent % 10 == 0:
        sys.stdout.write(f"\r...{percent}%")
        sys.stdout.flush()

models_dir = r"c:\Projects\VoiceGuardAI\backend\app\ml\models"

# Cleanup old data files
for old_f in ["aasist.onnx.data", "xlsr.onnx.data"]:
    p = os.path.join(models_dir, old_f)
    if os.path.exists(p):
        os.remove(p)
        print(f"Removed old external data file: {p}")

files = ["aasist.onnx", "xlsr.onnx"]
base_url = "https://huggingface.co/agh2005/VoiceGuardAI-models/resolve/main/"

for f in files:
    out_path = os.path.join(models_dir, f)
    print(f"\nDownloading {f} from {base_url + f}...")
    urllib.request.urlretrieve(base_url + f, out_path, reporthook=download_progress)
    print(f"\nDownloaded {f} to {out_path}")
