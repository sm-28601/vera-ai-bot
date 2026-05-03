"""
Decision Engine — selects the ONE strongest trigger to act on per merchant.

Priority-based, fully deterministic. No randomness.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from state import ContextStore, ConversationState, SuppressionManager


# Fixed priority map: lower number = higher priority
TRIGGER_PRIORITY = {
    "supply_alert": 1,
    "regulation_change": 2,
    "active_planning_intent": 3,
    "perf_dip": 4,
    "renewal_due": 5,
    "recall_due": 6,
    "chronic_refill_due": 7,
    "review_theme_emerged": 8,
    "perf_spike": 9,
    "ipl_match_today": 10,
    "competitor_opened": 11,
    "milestone_reached": 12,
    "research_digest": 13,
    "cde_opportunity": 14,
    "wedding_package_followup": 14,
    "trial_followup": 14,
    "festival_upcoming": 15,
    "seasonal_perf_dip": 16,
    "category_seasonal": 16,
    "curious_ask_due": 17,
    "dormant_with_vera": 18,
    "winback_eligible": 19,
    "gbp_unverified": 20,
    "customer_lapsed_soft": 8,
    "customer_lapsed_hard": 9,
    "appointment_tomorrow": 6,
}

DEFAULT_PRIORITY = 15


def select_triggers(
    available_trigger_ids: List[str],
    context_store: ContextStore,
    conversation_state: ConversationState,
    suppression: SuppressionManager,
    now_iso: str,
) -> List[Dict[str, Any]]:
    """
    Given available trigger IDs, select the best trigger(s) to act on.
    Returns a list of (trigger_payload, merchant_payload, category_payload, customer_payload) tuples.
    At most one trigger per merchant.
    """
    candidates = []
    ended_merchants = conversation_state.get_ended_merchants()

    for tid in available_trigger_ids:
        trigger = context_store.get("trigger", tid)
        if not trigger:
            continue

        # Skip expired triggers
        expires = trigger.get("expires_at", "")
        if expires and _is_expired(expires, now_iso):
            continue

        merchant_id = trigger.get("merchant_id")
        if not merchant_id:
            continue

        # Skip merchants who opted out
        if merchant_id in ended_merchants:
            continue

        # Skip already-suppressed triggers
        sup_key = trigger.get("suppression_key", "")
        if sup_key and suppression.is_suppressed(sup_key):
            continue

        # Skip if merchant has active conversation (don't stack)
        if conversation_state.has_active_conversation(merchant_id):
            continue

        merchant = context_store.get("merchant", merchant_id)
        if not merchant:
            continue

        cat_slug = merchant.get("category_slug", "")
        category = context_store.get("category", cat_slug)
        if not category:
            continue

        # Resolve customer if customer-scoped
        customer = None
        customer_id = trigger.get("customer_id")
        if customer_id:
            customer = context_store.get("customer", customer_id)

        # Calculate score
        score = _score_trigger(trigger, merchant)

        candidates.append({
            "trigger_id": tid,
            "trigger": trigger,
            "merchant_id": merchant_id,
            "merchant": merchant,
            "category": category,
            "customer_id": customer_id,
            "customer": customer,
            "score": score,
        })

    # Group by merchant, pick best per merchant
    best_per_merchant: Dict[str, Dict] = {}
    for c in candidates:
        mid = c["merchant_id"]
        if mid not in best_per_merchant or c["score"] > best_per_merchant[mid]["score"]:
            best_per_merchant[mid] = c

    # Sort by score descending, return ordered list
    result = sorted(best_per_merchant.values(), key=lambda x: x["score"], reverse=True)
    return result


def _score_trigger(trigger: dict, merchant: dict) -> float:
    """Compute a deterministic score for a trigger."""
    kind = trigger.get("kind", "")
    urgency = trigger.get("urgency", 1)
    base_priority = TRIGGER_PRIORITY.get(kind, DEFAULT_PRIORITY)

    # Invert priority (lower number = higher score)
    score = (25 - base_priority) * 10 + urgency * 5

    # Context boosts
    signals = merchant.get("signals", [])

    # Boost if merchant engaged recently
    if any("engaged_in_last_48h" in s or "engaged_in_last_24h" in s for s in signals):
        score += 15

    # Boost if trigger references merchant's active offer
    if kind in ("perf_spike", "ipl_match_today", "festival_upcoming"):
        active_offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
        if active_offers:
            score += 10

    # Boost for severe performance dips
    if kind == "perf_dip":
        delta = trigger.get("payload", {}).get("delta_pct", 0)
        if isinstance(delta, (int, float)) and delta < -0.30:
            score += 10

    # Boost for imminent renewal
    if kind == "renewal_due":
        days = trigger.get("payload", {}).get("days_remaining", 999)
        if isinstance(days, (int, float)) and days <= 7:
            score += 15

    # Boost for active planning (merchant already said yes)
    if kind == "active_planning_intent":
        score += 20

    return score


def _is_expired(expires_at: str, now_iso: str) -> bool:
    """Check if a trigger has expired."""
    try:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        return now > exp
    except (ValueError, TypeError):
        return False
