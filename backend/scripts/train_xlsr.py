import os
import random
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import soundfile as sf
from transformers import Wav2Vec2Model
from tqdm import tqdm

# Constants
SAMPLE_RATE = 16000
MAX_LENGTH_SEC = 3 # Reduced to 3s to save memory/compute (attention scales quadratically)
MIN_LENGTH_SEC = 2
MAX_LENGTH_SAMPLES = MAX_LENGTH_SEC * SAMPLE_RATE
MIN_LENGTH_SAMPLES = MIN_LENGTH_SEC * SAMPLE_RATE
BATCH_SIZE = 4 # Reduced to avoid VRAM swapping
GRADIENT_ACCUMULATION_STEPS = 4 # Emulates a batch size of 16
EPOCHS_STAGE1 = 3 # Fast head convergence
EPOCHS_STAGE2 = 5 # Short fine-tuning
LR_STAGE1 = 1e-3
LR_STAGE2 = 1e-5

class SpoofDataset(Dataset):
    def __init__(self, metadata_path, split="train"):
        super().__init__()
        # Load metadata
        df = pd.read_csv(metadata_path)
        self.df = df[df['split'] == split].reset_index(drop=True)
        self.base_dir = os.path.dirname(os.path.dirname(metadata_path)) # Assuming files are relative to some base

    def __len__(self):
        return len(self.df)

    def preprocess(self, waveform):
        # waveform shape: (num_samples,)
        num_frames = waveform.shape[0]
        
        # Cropping / Padding
        if num_frames > MAX_LENGTH_SAMPLES:
            start = random.randint(0, num_frames - MAX_LENGTH_SAMPLES)
            waveform = waveform[start:start + MAX_LENGTH_SAMPLES]
        elif num_frames < MIN_LENGTH_SAMPLES:
            pad_amount = MIN_LENGTH_SAMPLES - num_frames
            waveform = torch.nn.functional.pad(waveform, (0, pad_amount))
            
        return waveform

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        file_path = row['filepath']
        label = row['label'] # 0 for bonafide, 1 for spoof
        
        # Handle relative vs absolute paths
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.base_dir, file_path)

        # Load audio with soundfile (returns numpy array)
        data, sr = sf.read(file_path, dtype='float32')
        
        # If stereo, convert to mono
        if data.ndim > 1:
            data = data.mean(axis=1)
        
        waveform = torch.from_numpy(data)
        
        # Resample to 16kHz if needed
        if sr != SAMPLE_RATE:
            import scipy.signal
            num_samples = int(len(data) * SAMPLE_RATE / sr)
            resampled = scipy.signal.resample(waveform.numpy(), num_samples)
            waveform = torch.from_numpy(resampled.astype('float32'))

        waveform = self.preprocess(waveform)
        
        # Simple data augmentations could go here (noise, reverb, etc)
        # For brevity in standard training, we stick to clean first or add basic transforms.
        
        return waveform, torch.tensor(label, dtype=torch.long)

def collate_fn(batch):
    waveforms, labels = zip(*batch)
    
    # Pad within batch
    lengths = [w.shape[0] for w in waveforms]
    max_len = max(lengths)
    
    padded_waveforms = []
    for w in waveforms:
        pad_amount = max_len - w.shape[0]
        padded_waveforms.append(torch.nn.functional.pad(w, (0, pad_amount)))
        
    return torch.stack(padded_waveforms), torch.stack(labels)

class XlsrSpoofDetector(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-xls-r-300m")
        self.head = nn.Sequential(
            nn.Linear(1024, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 2)
        )

    def forward(self, x):
        outputs = self.backbone(x)
        # Mean pooling over time dimension
        hidden_states = outputs.last_hidden_state
        pooled = hidden_states.mean(dim=1) 
        logits = self.head(pooled)
        return logits
        
def train_epoch(model, dataloader, optimizer, criterion, device, accumulation_steps=4):
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    
    # Initialize scaler for mixed precision (Massive speedup on RTX 3050)
    scaler = torch.cuda.amp.GradScaler(enabled=device.type == 'cuda')
    
    pbar = tqdm(dataloader, desc="Training")
    for i, (batch_x, batch_y) in enumerate(pbar):
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)
        
        # Mixed precision forward pass
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == 'cuda'):
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss = loss / accumulation_steps # Normalize for accumulation
            
        # Mixed precision backward pass
        scaler.scale(loss).backward()
        
        # Step optimizer only after accumulating enough gradients
        if ((i + 1) % accumulation_steps == 0) or (i + 1 == len(dataloader)):
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()
        
        total_loss += loss.item() * accumulation_steps
        _, predicted = outputs.max(1)
        total += batch_y.size(0)
        correct += predicted.eq(batch_y).sum().item()
        
        pbar.set_postfix({'loss': loss.item() * accumulation_steps, 'acc': correct/total})
        
    return total_loss / len(dataloader), correct / total

def eval_epoch(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for batch_x, batch_y in tqdm(dataloader, desc="Evaluating"):
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += batch_y.size(0)
            correct += predicted.eq(batch_y).sum().item()
            
    return total_loss / len(dataloader), correct / total

def main():
    metadata_path = r'D:\voice_integrity\datasets\processed\master_metadata.csv'
    checkpoint_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'ml', 'checkpoints')
    os.makedirs(checkpoint_dir, exist_ok=True)
    best_model_path = os.path.join(checkpoint_dir, 'xlsr_spoof_best.pt')
    
    if not os.path.exists(metadata_path):
        print(f"Warning: Metadata file {metadata_path} not found. Ensure dataset is available.")
        # We can create a dummy one for testing the script if needed
        return

    print("Loading datasets...")
    train_dataset = SpoofDataset(metadata_path, split="train")
    val_dataset = SpoofDataset(metadata_path, split="val")
    
    # Windows multiprocessing overhead is high; use num_workers=0
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_fn, num_workers=0)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    model = XlsrSpoofDetector().to(device)
    
    # Calculate class weights for Focal Loss / Weighted CE
    # For now, using standard CE
    criterion = nn.CrossEntropyLoss()
    
    # ==========================
    # STAGE 1: Train Head Only
    # ==========================
    print("\n--- STAGE 1: Training Classification Head ---")
    for param in model.backbone.parameters():
        param.requires_grad = False
        
    optimizer = torch.optim.AdamW(model.head.parameters(), lr=LR_STAGE1)
    
    best_val_acc = 0.0
    for epoch in range(1, EPOCHS_STAGE1 + 1):
        print(f"\nEpoch {epoch}/{EPOCHS_STAGE1} (Stage 1)")
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, criterion, device, accumulation_steps=GRADIENT_ACCUMULATION_STEPS)
        val_loss, val_acc = eval_epoch(model, val_loader, criterion, device)
        
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")
        print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_model_path)
            print("Saved best model (Stage 1)!")

    # ==========================
    # STAGE 2: Train End-to-End
    # ==========================
    print("\n--- STAGE 2: Fine-tuning End-to-End ---")
    # Load best weights from Stage 1
    model.load_state_dict(torch.load(best_model_path))
    
    # Instead of unfreezing the ENTIRE model (very slow), we freeze the feature extractor 
    # and the first 12 layers of the transformer. We only fine-tune the top 12 layers.
    # This cuts compute time nearly in half and preserves general acoustic features!
    model.backbone.feature_extractor.requires_grad_(False)
    for i in range(12):
        model.backbone.encoder.layers[i].requires_grad_(False)
    for i in range(12, 24):
        model.backbone.encoder.layers[i].requires_grad_(True)
        
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR_STAGE2)
    
    for epoch in range(1, EPOCHS_STAGE2 + 1):
        print(f"\nEpoch {epoch}/{EPOCHS_STAGE2} (Stage 2)")
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, criterion, device, accumulation_steps=GRADIENT_ACCUMULATION_STEPS)
        val_loss, val_acc = eval_epoch(model, val_loader, criterion, device)
        
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")
        print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_model_path)
            print("Saved best model (Stage 2)!")

if __name__ == "__main__":
    main()
