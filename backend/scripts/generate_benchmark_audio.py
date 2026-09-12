"""
Script to generate multi-lingual benchmark audio samples for VoiceGuardAI.
Generates 16kHz mono WAV files for Hindi, Telugu, Tamil, Kannada, Bengali, and Indian English.
"""
import os
import io
from gtts import gTTS
import soundfile as sf
import librosa
import numpy as np

OUTPUT_DIR = os.path.abspath(r"c:\Projects\VoiceGuardAI\frontend\public\samples")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLES = [
    {
        "filename": "indian_english_high_value.wav",
        "text": "Good morning. This is Rajesh Kumar calling from Mumbai. Please process an urgent wire transfer of fifty thousand dollars immediately.",
        "lang": "en",
        "tld": "co.in",
        "title": "Indian English (Mumbai Business Accent)",
        "amount": 50000,
        "channel": "High-Value Wire Transfer",
        "location": "Mumbai, Maharashtra (IN)"
    },
    {
        "filename": "hindi_accent_bank_transfer.wav",
        "text": "नमस्ते, मैं दिल्ली कॉर्पोरेट शाखा से बात कर रहा हूँ। पचास हज़ार डॉलर का वायर ट्रांसफर तुरंत मंज़ूर कीजिए।",
        "lang": "hi",
        "tld": "com",
        "title": "Hindi (Northern Standard Dialect)",
        "amount": 50000,
        "channel": "RTGS / Urgent Wire",
        "location": "New Delhi, Delhi (IN)"
    },
    {
        "filename": "telugu_urgent_wire.wav",
        "text": "నమస్కారం, హైదరాబాద్ బ్రాంచ్ నుండి మాట్లాడుతున్నాను. దయచేసి మా వ్యాపార ఖాతా నుండి యాభై వేల డాలర్ల వైర్ బదిలీని వెంటనే ప్రాసెస్ చేయండి.",
        "lang": "te",
        "tld": "com",
        "title": "Telugu (Hyderabad Regional Dialect)",
        "amount": 50000,
        "channel": "High-Value Wire Transfer",
        "location": "Hyderabad, Telangana (IN)"
    },
    {
        "filename": "tamil_otp_override.wav",
        "text": "வணக்கம், சென்னை தலைமை அலுவலகத்திலிருந்து பேசுகிறேன். ஐம்பதாயிரம் டாலர் அவசர நிதி பரிமாற்றத்தை உடனடியாக அங்கீகரிக்கவும்.",
        "lang": "ta",
        "tld": "com",
        "title": "Tamil (Chennai Southern Dialect)",
        "amount": 50000,
        "channel": "High-Value Wire Transfer",
        "location": "Chennai, Tamil Nadu (IN)"
    },
    {
        "filename": "kannada_beneficiary_add.wav",
        "text": "ನಮಸ್ಕಾರ, ಬೆಂಗಳೂರು ಕಚೇರಿಯಿಂದ ಕರೆ ಮಾಡುತ್ತಿದ್ದೇನೆ. ದಯವಿಟ್ಟು ಐವತ್ತು ಸಾವಿರ ಡಾಲರ್ ತುರ್ತು ವರ್ಗಾವಣೆಯನ್ನು ತಕ್ಷಣವೇ ಅನುಮೋದಿಸಿ.",
        "lang": "kn",
        "tld": "com",
        "title": "Kannada (Bengaluru Regional Dialect)",
        "amount": 50000,
        "channel": "High-Value Wire Transfer",
        "location": "Bengaluru, Karnataka (IN)"
    },
    {
        "filename": "bengali_corporate_swift.wav",
        "text": "নমস্কার, কলকাতা কর্পোরেট শাখা থেকে বলছি। অবিলম্বে পঞ্চাশ হাজার ডলার আন্তর্জাতিক ওয়্যার ট্রান্সফার সম্পন্ন করুন।",
        "lang": "bn",
        "tld": "com",
        "title": "Bengali (Kolkata Eastern Dialect)",
        "amount": 50000,
        "channel": "SWIFT / International Wire",
        "location": "Kolkata, West Bengal (IN)"
    },
]

def main():
    print(f"Generating {len(SAMPLES)} benchmark audio files into: {OUTPUT_DIR}")
    for item in SAMPLES:
        out_path = os.path.join(OUTPUT_DIR, item["filename"])
        print(f"Generating {item['filename']} ({item['title']})...")
        try:
            tts_args = {"text": item["text"], "lang": item["lang"]}
            if "tld" in item and item["tld"]:
                tts_args["tld"] = item["tld"]
            tts = gTTS(**tts_args)
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            
            # Load with librosa at target 16kHz mono
            y, sr = librosa.load(mp3_fp, sr=16000, mono=True)
            
            # Normalize peak volume
            if np.max(np.abs(y)) > 0:
                y = y / np.max(np.abs(y)) * 0.90
            
            sf.write(out_path, y, 16000, subtype="PCM_16")
            print(f"  -> Saved {out_path} ({len(y)/16000:.2f}s, 16000Hz PCM_16)")
        except Exception as e:
            print(f"  -> Failed for {item['filename']}: {e}")
            # Fallback: create speech-like synthetic tone if internet unavailable
            dur = 3.5
            t = np.linspace(0, dur, int(16000 * dur), endpoint=False)
            f0 = 140.0
            y = 0.5 * np.sin(2 * np.pi * f0 * t) * np.exp(-t / 3.0)
            sf.write(out_path, y.astype(np.float32), 16000, subtype="PCM_16")
            print(f"  -> Saved synthetic fallback {out_path}")

if __name__ == "__main__":
    main()
