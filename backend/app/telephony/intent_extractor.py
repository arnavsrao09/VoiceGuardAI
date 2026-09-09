"""
Speech & Conversation Intent Extractor for VoiceGuardAI.

Real-time analysis of live speech transcripts to extract:
1. Requested Transaction Amount (handles English, Telugu, Kannada, Hindi digits and spoken words)
2. Transaction Channel (Wire Transfer, PIN Reset, Privileged System Access)
3. Urgency & Coercion Indicators (Scam/Pressure Tactics detection)
"""

from __future__ import annotations

import re
from typing import TypedDict


class ExtractedIntent(TypedDict):
    raw_text: str
    detected_amount: float | None
    formatted_amount: str | None
    detected_channel: str
    urgency_level: str  # "NORMAL", "ELEVATED", "CRITICAL"
    urgency_cues: list[str]
    coercion_cues: list[str]
    intent_summary: str
    confidence: float


# Indian Numeral Maps
TELUGU_DIGITS = {'౦': '0', '౧': '1', '౨': '2', '౩': '3', '౪': '4', '౫': '5', '౬': '6', '౭': '7', '౮': '8', '౯': '9'}
KANNADA_DIGITS = {'೦': '0', '೧': '1', '೨': '2', '೩': '3', '೪': '4', '೫': '5', '೬': '6', '೭': '7', '೮': '8', '೯': '9'}
DEVANAGARI_DIGITS = {'०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'}

# Word-to-number mapping for spoken English, Telugu, Kannada, and Hindi numbers
WORD_NUMBER_VALUES = {
    # English
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000, "lakh": 100000, "million": 1000000,
    "crore": 10000000, "billion": 1000000000,
    
    # Telugu (తెలుగు) & Transliterated
    "ఒకటి": 1, "ఒక": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5,
    "ఆరు": 6, "ఏడు": 7, "ఎనిమిది": 8, "తొమ్మిది": 9, "పది": 10,
    "ఇరవై": 20, "ముప్పై": 30, "నలభై": 40, "యాభై": 50, "అరవై": 60,
    "డెబ్బై": 70, "ఎనభై": 80, "తొంభై": 90, "వంద": 100, "వందలు": 100,
    "వేయి": 1000, "వేలు": 1000, "వేల": 1000, "లక్ష": 100000, "లక్షలు": 100000, "కోటి": 10000000,
    "okati": 1, "rendu": 2, "moodu": 3, "nalugu": 4, "aidu": 5,
    "padi": 10, "iravai": 20, "muppai": 30, "nalabhai": 40, "yabhai": 50, "yabai": 50,
    "vanda": 100, "veyi": 1000, "velu": 1000, "vela": 1000, "laksha": 100000, "koti": 10000000,
    
    # Kannada (ಕನ್ನಡ) & Hindi (हिंदी)
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5, "ಹತ್ತು": 10, "ಇಪ್ಪತ್ತು": 20, "ಐವತ್ತು": 50,
    "ನೂರು": 100, "ಸಾವಿರ": 1000, "saavira": 1000,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "दस": 10, "बीस": 20, "पचास": 50,
    "सौ": 100, "हजार": 1000, "लाख": 100000, "करोड़": 10000000, "hazar": 1000,
}


def normalize_indian_numerals(text: str) -> str:
    """Normalize Telugu, Kannada, and Devanagari numerals to standard ASCII 0-9."""
    for k, v in TELUGU_DIGITS.items():
        text = text.replace(k, v)
    for k, v in KANNADA_DIGITS.items():
        text = text.replace(k, v)
    for k, v in DEVANAGARI_DIGITS.items():
        text = text.replace(k, v)
    return text


def parse_spoken_number(phrase: str) -> float | None:
    """Convert natural spoken number phrases to float across English, Telugu, Kannada, and Hindi."""
    tokens = re.findall(r'[^\s,.;:!?()]+', phrase.lower())
    if not tokens:
        return None

    total = 0.0
    current = 0.0
    found_any = False

    for word in tokens:
        if word in WORD_NUMBER_VALUES:
            val = WORD_NUMBER_VALUES[word]
            found_any = True
            if val in (1000, 100000, 1000000, 10000000, 1000000000):
                if current == 0:
                    current = 1
                total += current * val
                current = 0
            elif val == 100:
                if current == 0:
                    current = 1
                current *= val
            else:
                current += val

    total += current
    return total if found_any and total > 0 else None


def extract_transaction_amount(text: str) -> float | None:
    """
    Extract transaction money amount from text in English, Telugu, Kannada, and Hindi.
    Handles:
    - Currency symbols: $50,000, ₹50,000, 50,000రూ, ₹50వేలు
    - Telugu words: యాభై వేల రూపాయలు, 50 వేలు, 2 లక్షలు, 1 కోటి
    - Spoken numbers & English formats
    """
    text = normalize_indian_numerals(text)
    text_lower = text.lower()

    # 1. Look for explicit currency amounts: $50,000 or ₹50000 or 50,000/-
    dollar_match = re.search(r'[\$€£₹]\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)', text)
    if dollar_match:
        val_str = dollar_match.group(1).replace(',', '')
        try:
            return float(val_str)
        except ValueError:
            pass

    # 2. Look for 'k' shorthand: 50k, 250k, 5k
    k_match = re.search(r'\b([0-9]+(?:\.[0-9]+)?)\s*k\b', text_lower)
    if k_match:
        try:
            return float(k_match.group(1)) * 1000
        except ValueError:
            pass

    # 3. Look for numbers followed by Indian / Global currency units or Telugu/Kannada denominations:
    # e.g. 50 వేలు, 50 వేల, 2 లక్షలు, 50000 రూపాయలు, 50 thousand, 50k
    unit_regex = (
        r'([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\s*'
        r'(thousand|lakh|million|crore|dollars?|usd|rupees?|bucks?|'
        r'వేలు|వేల|లక్ష|లక్షలు|కోటి|కోట్లు|రూపాయలు|రూ|'
        r'ಸಾವಿರ|ಲಕ್ಷ|ಕೋಟಿ|ರೂಪಾಯಿ|हजार|लाख|करोड़|रुपये|रु)'
    )
    num_denom_match = re.search(unit_regex, text_lower, re.UNICODE)
    if num_denom_match:
        raw_num = float(num_denom_match.group(1).replace(',', ''))
        unit = num_denom_match.group(2)
        if unit in ('thousand', 'వేలు', 'వేల', 'ಸಾವಿರ', 'हजार'):
            return raw_num * 1000
        elif unit in ('lakh', 'లక్ష', 'లక్షలు', 'लाख'):
            return raw_num * 100000
        elif unit in ('million',):
            return raw_num * 1000000
        elif unit in ('crore', 'కోటి', 'కోట్లు', 'ಕೋಟಿ', 'करोड़'):
            return raw_num * 10000000
        return raw_num

    # 4. Spoken word parsing across English, Telugu, Kannada, Hindi:
    # e.g. 'యాభై వేల రూపాయలు', 'yabhai velu', 'fifty thousand dollars'
    tokens = re.findall(r'[^\s,.;:!?()]+', text_lower)
    curr_seq = []
    best_amount = None
    for token in tokens:
        if token in WORD_NUMBER_VALUES:
            curr_seq.append(token)
        else:
            if curr_seq:
                parsed = parse_spoken_number(' '.join(curr_seq))
                if parsed and parsed >= 1:
                    best_amount = parsed
                    break
                curr_seq = []
    if curr_seq and not best_amount:
        parsed = parse_spoken_number(' '.join(curr_seq))
        if parsed and parsed >= 1:
            best_amount = parsed

    if best_amount is not None:
        return best_amount

    # 5. Fallback: bare standalone number (e.g. "10000", "25,000", "1,00,000")
    #    Catches plain amounts from speech without currency symbols or unit words.
    bare_match = re.search(r'\b([0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3}|[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,})\b', text)
    if bare_match:
        val_str = bare_match.group(1).replace(',', '')
        try:
            val = float(val_str)
            if val >= 100:
                return val
        except ValueError:
            pass

    return None


def extract_transaction_channel(text: str) -> str:
    """Identify the banking channel or sensitive action requested in English or Telugu."""
    text_lower = text.lower()

    # Wire / Fund Transfer (English & Telugu: ట్రాన్స్‌ఫర్, పంపండి, బదిలీ, డబ్బులు, ఖాతాలోకి)
    wire_keywords = [
        "wire", "wire transfer", "swift", "fund transfer", "transfer funds", "send money",
        "move money", "rtgs", "neft", "remit", "transfer",
        "ట్రాన్స్‌ఫర్", "ట్రాన్స్ఫర్", "పంపండి", "పంపు", "బదిలీ", "డబ్బులు", "డబ్బు", "ఖాతాలోకి", "చెల్లింపు",
        "వర్ಗಾವಣೆ", "ಕಳುಹಿಸಿ", "ಹಣ", "भेजें", "ट्रांसफर", "पैसे"
    ]
    if any(k in text_lower for k in wire_keywords):
        return "High-Value Wire Transfer"

    # PIN / Password / Credential Reset (English & Telugu: పిన్ రీసెట్, పాస్‌వర్డ్, ఓటీపీ, అన్‌లాక్)
    pin_keywords = [
        "pin reset", "reset pin", "change pin", "password reset", "reset password",
        "credentials", "otp", "unlock account", "pin", "password",
        "పిన్", "పిన్ రీసెట్", "పాస్‌వర్డ్", "పాస్వర్డ్", "ఓటీపీ", "అన్‌లాక్", "ఖాతా లాక్",
        "ಪಿನ್", "ಪಾಸ್‌ವರ್ಡ್", "ಒಟಿಪಿ", "पिन", "पासवर्ड", "ओटीपी"
    ]
    if any(k in text_lower for k in pin_keywords):
        return "Account PIN Reset"

    # Privileged Admin Access (English & Telugu: అధికారిక యాక్సెస్, అడ్మిన్)
    admin_keywords = [
        "admin access", "system access", "privileged access", "root access", "override",
        "executive override", "authorize access",
        "అధికారిక యాక్సెస్", "అడ్మిన్", "సిస్టమ్ యాక్సెస్", "సిస్టమ్",
        "ಆಡಳಿತ", "ಸಿಸ್ಟಮ್", "व्यवस्थापक"
    ]
    if any(k in text_lower for k in admin_keywords):
        return "Privileged System Access"

    return "High-Value Wire Transfer"  # Default financial action


def extract_urgency_and_coercion(text: str) -> tuple[str, list[str], list[str]]:
    """Scan transcript for pressure tactics, urgency markers, and social engineering coercion in English and Telugu."""
    text_lower = text.lower()

    urgency_terms = [
        # English
        "urgent", "urgently", "immediate", "immediately", "right now", "asap",
        "emergency", "hurry", "quickly", "without delay", "critical", "deadline",
        # Telugu
        "వెంటనే", "త్వరగా", "ఇప్పుడే", "అత్యవసరం", "ఆలస్యం లేకుండా", "ముఖ్యమైన",
        "ventane", "twaraga", "ippude",
        # Kannada & Hindi
        "ತಕ್ಷಣ", "ಬೇಗ", "जरूरी", "तुरंत", "जल्दी",
    ]

    coercion_terms = [
        # English
        "police", "cbi", "fbi", "arrest", "warrant", "tax fraud", "court",
        "confidential", "don't tell", "penalty", "freeze", "lawsuit",
        # Telugu
        "పోలీస్", "పోలీసులు", "సిబిఐ", "అరెస్ట్", "కోర్టు", "జరిమానా", "ఫ్రీజ్",
        "బ్లాక్", "ఎవరికీ చెప్పవద్దు", "రహస్యం", "కేసు",
        # Kannada & Hindi
        "ಪೊಲೀಸ್", "ಬಂಧನ", "पुलिस", "गिरफ्तार", "सीबीआई", "अदालत",
    ]

    urgency_found = [term for term in urgency_terms if term in text_lower]
    coercion_found = [term for term in coercion_terms if term in text_lower]

    if coercion_found or len(urgency_found) >= 2:
        level = "CRITICAL"
    elif urgency_found:
        level = "ELEVATED"
    else:
        level = "NORMAL"

    return level, urgency_found, coercion_found


def analyze_conversation_transcript(text: str) -> ExtractedIntent:
    """Comprehensive intent extraction pipeline on conversation text."""
    if not text or not text.strip():
        return ExtractedIntent(
            raw_text="",
            detected_amount=None,
            formatted_amount=None,
            detected_channel="High-Value Wire Transfer",
            urgency_level="NORMAL",
            urgency_cues=[],
            coercion_cues=[],
            intent_summary="No audible speech detected yet.",
            confidence=0.0,
        )

    amount = extract_transaction_amount(text)
    channel = extract_transaction_channel(text)
    urgency_level, urgency_cues, coercion_cues = extract_urgency_and_coercion(text)

    formatted_amount = f"₹{amount:,.0f}" if amount is not None else None

    # Construct descriptive summary
    parts = []
    if amount is not None:
        parts.append(f"Amount: {formatted_amount}")
    parts.append(f"Channel: {channel}")
    if urgency_level != "NORMAL":
        parts.append(f"Pressure Flags: {', '.join(urgency_cues + coercion_cues)}")

    summary = " · ".join(parts)

    confidence = 0.90 if amount is not None else 0.65

    return ExtractedIntent(
        raw_text=text.strip(),
        detected_amount=amount,
        formatted_amount=formatted_amount,
        detected_channel=channel,
        urgency_level=urgency_level,
        urgency_cues=urgency_cues,
        coercion_cues=coercion_cues,
        intent_summary=summary,
        confidence=confidence,
    )
