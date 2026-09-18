import os
import sys
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import roc_curve, auc, brier_score_loss
import numpy as np
from tqdm import tqdm
import onnx
import onnxruntime as ort

# We can import the dataset and model definition from train_xlsr
# Ensure we run this from the project root or adjust path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
try:
    from backend.scripts.train_xlsr import XlsrSpoofDetector, SpoofDataset, collate_fn  # type: ignore[import-not-found]
except ImportError:
    # Fallback if run directly from scripts folder
    from train_xlsr import XlsrSpoofDetector, SpoofDataset, collate_fn  # type: ignore[import-not-found]

BATCH_SIZE = 8

def compute_eer(label, pred, positive_label=1):
    fpr, tpr, threshold = roc_curve(label, pred, pos_label=positive_label)
    fnr = 1 - tpr
    eer_threshold = threshold[np.nanargmin(np.absolute((fnr - fpr)))]
    eer = fpr[np.nanargmin(np.absolute((fnr - fpr)))]
    return eer, eer_threshold, fpr, fnr, threshold

def evaluate_and_export():
    print("--- XLS-R Evaluation and Export ---")
    
    # Paths
    checkpoint_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'ml', 'checkpoints')
    model_path = os.path.join(checkpoint_dir, 'xlsr_spoof_best.pt')
    metadata_path = r'D:\voice_integrity\datasets\processed\master_metadata.csv'
    export_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'ml', 'models')
    export_path = os.path.join(export_dir, 'xlsr.onnx')
    
    if not os.path.exists(model_path):
        print(f"Error: Trained model not found at {model_path}")
        return
        
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    print("Loading model...")
    model = XlsrSpoofDetector()
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    
    if os.path.exists(metadata_path):
        print("Loading test dataset for evaluation...")
        test_dataset = SpoofDataset(metadata_path, split="test")
        test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_fn)
        
        all_labels = []
        all_preds = []
        
        print("Evaluating on test set...")
        with torch.no_grad():
            for batch_x, batch_y in tqdm(test_loader):
                batch_x = batch_x.to(device)
                logits = model(batch_x)
                probs = torch.softmax(logits, dim=1)[:, 1] # Probability of being spoof (class 1)
                
                all_labels.extend(batch_y.numpy())
                all_preds.extend(probs.cpu().numpy())
                
        all_labels = np.array(all_labels)
        all_preds = np.array(all_preds)
        
        # Calculate Metrics
        fpr, tpr, thresholds = roc_curve(all_labels, all_preds)
        roc_auc = auc(fpr, tpr)
        eer, eer_threshold, _, _, _ = compute_eer(all_labels, all_preds)
        
        print(f"\nEvaluation Results:")
        print(f"ROC-AUC: {roc_auc:.4f}")
        print(f"EER: {eer:.4f} (at threshold {eer_threshold:.4f})")
        print(f"Brier Score: {brier_score_loss(all_labels, all_preds):.4f}")
        
        optimal_threshold = eer_threshold
        print(f"\nRecommended DEEPFAKE_THRESHOLD for config: {optimal_threshold:.4f}")
    else:
        print(f"Metadata not found at {metadata_path}. Skipping evaluation and proceeding to export.")
        optimal_threshold = 0.5 # Default

    print("\nExporting model to ONNX...")
    # XLS-R typically takes (batch_size, sequence_length) as input
    # Assuming 16kHz, 4 seconds = 64000 samples
    dummy_input = torch.randn(1, 64000).to(device)
    
    os.makedirs(export_dir, exist_ok=True)
    
    try:
        torch.onnx.export(
            model,
            dummy_input,
            export_path,
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=['input_values'],
            output_names=['logits'],
            dynamic_axes={'input_values': {0: 'batch', 1: 'time'}, 'logits': {0: 'batch'}}
        )
        print(f"Successfully exported XLS-R to {export_path}")
        
        # Verify ONNX model
        print("Verifying ONNX export...")
        onnx_model = onnx.load(export_path)
        onnx.checker.check_model(onnx_model)
        
        # Compare PyTorch and ONNX outputs
        ort_session = ort.InferenceSession(export_path)
        
        # Get PyTorch output
        with torch.no_grad():
            torch_out = model(dummy_input)
            
        # Get ONNX output
        ort_inputs = {ort_session.get_inputs()[0].name: dummy_input.cpu().numpy()}
        ort_outs = ort_session.run(None, ort_inputs)
        
        # Compare
        np.testing.assert_allclose(torch_out.cpu().numpy(), ort_outs[0], rtol=1e-03, atol=1e-05)
        print("ONNX verification successful! PyTorch and ONNX outputs match.")
        
    except Exception as e:
        print(f"ONNX export or verification failed: {e}")

if __name__ == '__main__':
    evaluate_and_export()
