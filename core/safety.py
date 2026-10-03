"""Plain-code safety rules. No LLM is involved, so they cannot be talked around."""
import re
from typing import Optional

EMERGENCY_NUMBERS = "Rescue 1122 (available in many cities) or Edhi 115. Check which number works in your area."

DISCLAIMER = ("Informational only, not a diagnosis. This tool cannot replace a doctor. "
              "Fees are estimates, so call the clinic to confirm.")

# (pattern, kind). ASCII patterns use word boundaries; Urdu script is matched as a substring.
_EMERGENCY = [
    r"chest pain", r"pain in (my )?chest", r"chest tightness", r"seene mein (shadeed )?dard", r"سینے میں درد",
    r"can'?t breathe", r"cannot breathe", r"can'?t catch (my )?breath", r"severe (difficulty|trouble) breathing",
    r"saans (nahi|band)", r"سانس نہیں",
    r"unconscious", r"passed out", r"behosh", r"بے ہوش",
    r"heavy bleeding", r"bleeding (a lot|heavily|badly)", r"won'?t stop bleeding", r"vomiting blood", r"coughing (up )?blood",
    r"blood in (my )?vomit", r"khoon ki ulti", r"khoon (beh|bah) raha",
    r"face droop", r"slurred speech", r"sudden weakness (on )?one side", r"can'?t move (my )?(arm|leg)",
    r"seizure", r"convulsion", r"\b(had|having|has|got) (a )?fits?\b", r"daura",
    r"snake ?bite", r"poison", r"overdose", r"swallowed (bleach|pills)",
    r"choking", r"severe allergic", r"swelling of (the )?(face|lips|tongue|throat)",
    r"baby (is )?(not|isn'?t) breathing", r"newborn.*fever",
]
_SELF_HARM = [
    r"suicid", r"kill myself", r"end my life", r"want to die", r"self[- ]?harm", r"hurt myself",
    r"khudkushi", r"jaan de", r"marna chahta", r"marna chahti", r"خودکشی",
]


def _hit(patterns, text: str) -> Optional[str]:
    low = text.lower()
    for p in patterns:
        m = re.search(p, low)
        if m:
            return m.group(0)
    return None


def check_emergency(text: str) -> Optional[dict]:
    """Return {'kind','reason','message'} when the text needs an emergency response."""
    if _hit(_SELF_HARM, text):
        return {"kind": "self_harm", "reason": "Self-harm wording detected",
                "message": ("You are not alone, and help is available right now. If you might act on these thoughts, "
                            f"call your local emergency number immediately ({EMERGENCY_NUMBERS}) or go to the nearest "
                            "emergency room. Please tell a trusted family member or friend and stay with someone. "
                            "A psychiatrist or psychologist can help once you are safe.")}
    hit = _hit(_EMERGENCY, text)
    if hit:
        return {"kind": "medical", "reason": f"Emergency sign detected: \"{hit}\"",
                "message": (f"These symptoms can be life-threatening. Go to the nearest emergency room now or call "
                            f"{EMERGENCY_NUMBERS} Do not wait and do not drive yourself.")}
    return None
