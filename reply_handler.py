"""Multi-turn reply handler — auto-reply detection, intent transition, hostile exit."""
from __future__ import annotations
from typing import Dict, Optional
from state import ConversationState, ContextStore

AUTO_REPLY_PATTERNS = [
    "thank you for contacting", "our team will respond",
    "automated", "auto-reply", "we will get back",
    "aapki jaankari ke liye", "hamari team tak pahuncha",
    "we are currently unavailable", "leave a message",
]

HOSTILE_PATTERNS = [
    "stop messaging", "stop sending", "not interested",
    "spam", "useless", "don't message", "do not message",
    "unsubscribe", "remove me", "block",
]

COMMIT_PATTERNS = [
    "let's do it", "lets do it", "go ahead", "yes do it",
    "ok do it", "proceed", "yes please", "haan karo",
    "yes, send", "yes send", "confirm", "do it",
    "what's next", "whats next", "ok next",
]

OFFTOPIC_PATTERNS = [
    "gst", "tax filing", "income tax", "loan", "insurance",
    "can you also help me with",
]


def handle_reply(
    conversation_id: str,
    merchant_message: str,
    conversation_state: ConversationState,
    context_store: ContextStore,
) -> dict:
    """
    Process a merchant/customer reply and return the bot's next action.
    Returns: {action: "send"|"wait"|"end", body?, cta?, rationale}
    """
    msg_lower = merchant_message.strip().lower()
    conv = conversation_state.get(conversation_id)
    merchant_id = conv.get("merchant_id", "") if conv else ""
    trigger_id = conv.get("trigger_id", "") if conv else ""

    # --- Auto-reply detection ---
    if _is_auto_reply(msg_lower):
        count = conversation_state.increment_auto_reply(conversation_id)
        if count >= 3:
            conversation_state.set_status(conversation_id, "ended")
            return {
                "action": "end",
                "rationale": f"Auto-reply {count}x in a row, no real reply. Closing conversation."
            }
        elif count >= 2:
            return {
                "action": "wait",
                "wait_seconds": 86400,
                "rationale": f"Same auto-reply {count}x → owner not at phone. Wait 24h before retry."
            }
        else:
            return {
                "action": "send",
                "body": "Looks like an auto-reply. When the owner sees this, just reply 'Yes' to continue.",
                "cta": "binary_yes_no",
                "rationale": "Detected auto-reply; one explicit prompt to flag for owner."
            }

    # --- Hostile / opt-out detection ---
    if _is_hostile(msg_lower):
        conversation_state.set_status(conversation_id, "ended")
        return {
            "action": "send",
            "body": "Apologies — I won't message again. If anything changes, you can always restart with 'Hi Vera'.",
            "cta": "none",
            "rationale": "Merchant frustration explicit; one-line apology + opt-out path; closing."
        }

    # --- Off-topic detection ---
    if _is_offtopic(msg_lower):
        trigger = context_store.get("trigger", trigger_id) if trigger_id else None
        topic = trigger.get("kind", "our earlier topic").replace("_", " ") if trigger else "our earlier topic"
        return {
            "action": "send",
            "body": f"I'll have to leave that to your specialist — it's outside what I can help with. Coming back to {topic} — shall I continue?",
            "cta": "open_ended",
            "rationale": "Out-of-scope ask politely declined; redirects to original trigger thread."
        }

    # --- Commitment / intent transition ---
    if _is_commitment(msg_lower):
        merchant = context_store.get("merchant", merchant_id) if merchant_id else {}
        trigger = context_store.get("trigger", trigger_id) if trigger_id else {}
        cust_agg = merchant.get("customer_aggregate", {}) if merchant else {}
        count_str = ""
        if cust_agg.get("high_risk_adult_count"):
            count_str = f" ({cust_agg['high_risk_adult_count']} patients in scope)"
        elif cust_agg.get("total_unique_ytd"):
            count_str = f" ({cust_agg['total_unique_ytd']} customers in scope)"
        return {
            "action": "send",
            "body": f"Great — drafting now. I'll have it ready in under 2 minutes{count_str}. Reply CONFIRM to send, or EDIT if you want changes.",
            "cta": "binary_confirm_cancel",
            "rationale": "Merchant committed; switching to action-execution mode. Concrete scope + timeline."
        }

    # --- Simple affirmative (yes, ok, sure) ---
    if msg_lower.strip() in ("yes", "ok", "sure", "haan", "ha", "ji", "go", "done"):
        return {
            "action": "send",
            "body": "On it — drafting now. Will share in under 2 minutes for your review.",
            "cta": "open_ended",
            "rationale": "Simple affirmative acknowledged; moving to execution."
        }

    # --- Engaged response (question or substantive reply) ---
    # Default: acknowledge + advance conversation
    conversation_state.add_turn(conversation_id, "merchant", merchant_message)
    return {
        "action": "send",
        "body": f"Got it. Let me work on that based on what you've shared. I'll have something ready shortly — just reply GO when you want me to proceed.",
        "cta": "open_ended",
        "rationale": "Engaged merchant reply acknowledged; advancing conversation with low-friction next step."
    }


def _is_auto_reply(msg: str) -> bool:
    return any(p in msg for p in AUTO_REPLY_PATTERNS)

def _is_hostile(msg: str) -> bool:
    return any(p in msg for p in HOSTILE_PATTERNS)

def _is_commitment(msg: str) -> bool:
    return any(p in msg for p in COMMIT_PATTERNS)

def _is_offtopic(msg: str) -> bool:
    return any(p in msg for p in OFFTOPIC_PATTERNS)
