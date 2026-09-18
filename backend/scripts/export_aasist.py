import os
import sys

# Force UTF-8 encoding on Windows console for PyTorch ONNX prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import torch

# Add the voice_integrity path so we can import the model definition
sys.path.append(r'D:\voice_integrity')

try:
    from aasist_model import Model  # type: ignore[import-not-found]  # Resolved at runtime via sys.path
except ImportError as e:
    print(f"Error importing aasist_model: {e}")
    print("Please ensure D:\voice_integrity exists and contains aasist_model.py")
    sys.exit(1)

def export_aasist():
    # Paths
    checkpoint_path = r'D:\voice_integrity\checkpoints\aasist_robust_best.pth'
    export_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'ml', 'models')
    export_path = os.path.join(export_dir, 'aasist.onnx')

    os.makedirs(export_dir, exist_ok=True)

    if not os.path.exists(checkpoint_path):
        print(f"Error: Checkpoint not found at {checkpoint_path}")
        sys.exit(1)

    print(f"Loading AASIST model from {checkpoint_path}...")
    
    # Initialize the model (you might need to provide a config dictionary if required by aasist_model.py)
    # The default AASIST often requires a config dictionary. Let's try to load the state dict directly
    # and infer if there are missing args, or if we can load it.
    
    # Let's see how it was saved. Often it's a dict containing 'model_state_dict' or similar.
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    # Depending on the aasist implementation, we might need a config.
    # Usually, we instantiate it:
    # model = Model(config)
    # But without knowing the config, we might need to load it dynamically if it's saved in the checkpoint.
    # We will assume a default initialization or try to read it from the checkpoint.
    
    # Since we don't have the exact aasist_model.py right now, we will assume a generic init
    # If the user has a specific init, we might need to adjust this.
    try:
        from aasist_model import AASIST_CONFIG  # type: ignore[import-not-found]
        model = Model(AASIST_CONFIG) 
    except Exception as e:
        print(f"Error initializing model: {e}")
        print("Model initialization might require specific config arguments. Please update export_aasist.py if needed.")
        return

    # Extract state dict if it's nested
    state_dict = checkpoint
    if isinstance(checkpoint, dict):
        if 'model_state_dict' in checkpoint:
            state_dict = checkpoint['model_state_dict']
        elif 'state_dict' in checkpoint:
            state_dict = checkpoint['state_dict']
        
    # Remove 'module.' prefix if it was trained with DataParallel
    from collections import OrderedDict
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k[7:] if k.startswith('module.') else k
        new_state_dict[name] = v
        
    model.load_state_dict(new_state_dict)
    model.eval()

    print("Exporting model to ONNX...")
    # AASIST typically takes (batch_size, num_samples) as input
    # Assuming 16kHz, 4 seconds = 64000 samples
    dummy_input = torch.randn(1, 64000)
    
    try:
        torch.onnx.export(
            model,
            dummy_input,
            export_path,
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size', 1: 'num_samples'}, 'output': {0: 'batch_size'}}
        )
        print(f"Successfully exported AASIST to {export_path}")
    except Exception as e:
        print(f"ONNX export failed: {e}")

if __name__ == '__main__':
    export_aasist()
