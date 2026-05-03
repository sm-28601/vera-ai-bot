"""
Category voice profiles and formatting utilities.

Each category has specific tone, vocabulary, taboos, and salutation rules.
Used by the composer to ensure category-fit scoring.
"""
from __future__ import annotations
from typing import Optional


# ---------------------------------------------------------------------------
# Voice profile definitions (derived from dataset/categories/*.json)
# ---------------------------------------------------------------------------

VOICE_PROFILES = {
    "dentists": {
        "tone": "peer_clinical",
        "register": "respectful_collegial",
        "salutation": "Dr. {owner}",
        "code_mix": True,
        "taboos": {"guaranteed", "100% safe", "completely cure", "miracle",
                   "best in city", "doctor approved"},
        "domain_vocab": ["fluoride varnish", "scaling", "caries", "bruxism",
                         "endodontic", "periodontal", "aligner", "OPG", "RCT"],
        "emoji_ok": False,
        "source_citation_required": True,
    },
    "salons": {
        "tone": "warm_practical",
        "register": "approachable_expert",
        "salutation": "Hi {owner}",
        "code_mix": True,
        "taboos": {"guaranteed glow", "permanent results", "instant transformation",
                   "miracle", "best in city"},
        "domain_vocab": ["balayage", "keratin", "smoothening", "hair spa",
                         "olaplex", "threading", "waxing", "facial"],
        "emoji_ok": True,
        "source_citation_required": False,
    },
    "restaurants": {
        "tone": "warm_busy_practical",
        "register": "fellow_operator",
        "salutation": "Hi {owner}",
        "code_mix": True,
        "taboos": {"best food in city", "guaranteed packed house",
                   "miracle marketing", "viral guarantee"},
        "domain_vocab": ["footfall", "covers", "AOV", "table turnover",
                         "reservations", "happy hour", "thali"],
        "emoji_ok": True,
        "source_citation_required": False,
    },
    "gyms": {
        "tone": "energetic_disciplined",
        "register": "coach_to_member",
        "salutation": "Hi {owner}",
        "code_mix": False,  # english primary
        "taboos": {"guaranteed weight loss", "shred in 7 days",
                   "miracle transformation", "fastest results"},
        "domain_vocab": ["membership churn", "PT sessions", "HIIT",
                         "functional", "yoga", "pilates", "trial-to-paid"],
        "emoji_ok": True,
        "source_citation_required": False,
    },
    "pharmacies": {
        "tone": "trustworthy_precise",
        "register": "neighbourhood_pharmacist",
        "salutation": "Hi {owner}",
        "code_mix": True,
        "taboos": {"miracle cure", "guaranteed result", "100% safe",
                   "best price"},
        "domain_vocab": ["OTC", "schedule H", "generic", "molecule",
                         "MRP", "batch", "pharmacist counsel"],
        "emoji_ok": False,
        "source_citation_required": True,
    },
}


def get_voice(category_slug: str) -> dict:
    """Get the voice profile for a category."""
    return VOICE_PROFILES.get(category_slug, VOICE_PROFILES["restaurants"])


def format_salutation(category_slug: str, merchant: dict) -> str:
    """Generate the correct salutation for a merchant."""
    voice = get_voice(category_slug)
    owner = _get_owner_name(merchant)
    return voice["salutation"].format(owner=owner)


def format_customer_salutation(customer: dict, merchant: dict) -> str:
    """Generate a customer-facing salutation."""
    cust_name = customer.get("identity", {}).get("name", "")
    merchant_name = merchant.get("identity", {}).get("name", "")
    return f"Hi {cust_name}"


def get_merchant_attribution(merchant: dict) -> str:
    """Get the 'from' line for customer-facing messages."""
    owner = _get_owner_name(merchant)
    name = merchant.get("identity", {}).get("name", "")
    return f"{owner} from {name}" if owner else name


def check_taboos(category_slug: str, text: str) -> list[str]:
    """Check text for taboo words. Returns list of violations."""
    voice = get_voice(category_slug)
    violations = []
    text_lower = text.lower()
    for taboo in voice["taboos"]:
        if taboo.lower() in text_lower:
            violations.append(taboo)
    return violations


def should_use_hindi_mix(merchant: dict, customer: Optional[dict] = None) -> bool:
    """Determine if Hindi-English mix should be used."""
    if customer:
        lang = customer.get("identity", {}).get("language_pref", "")
        if "hi" in lang.lower():
            return True
    langs = merchant.get("identity", {}).get("languages", [])
    return "hi" in langs


def _get_owner_name(merchant: dict) -> str:
    """Extract owner first name from merchant context."""
    return merchant.get("identity", {}).get("owner_first_name", "")


def _get_merchant_name(merchant: dict) -> str:
    return merchant.get("identity", {}).get("name", "")


def _get_locality(merchant: dict) -> str:
    return merchant.get("identity", {}).get("locality", "")


def _get_city(merchant: dict) -> str:
    return merchant.get("identity", {}).get("city", "")
