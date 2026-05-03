"""
VERA AI — Merchant Assistant Bot
FastAPI server with 5 endpoints for the magicpin AI Challenge.
Run: uvicorn bot:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel

from state import ContextStore, ConversationState, SuppressionManager
from decision_engine import select_triggers
from compose import compose
from reply_handler import handle_reply

app = FastAPI(title="VERA AI Bot", version="1.0.0")
START = time.time()

# Global state
ctx_store = ContextStore()
conv_state = ConversationState()
suppression = SuppressionManager()


# ── Pydantic Models ──────────────────────────────────────────────────────

class ContextBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str

class TickBody(BaseModel):
    now: str
    available_triggers: List[str] = []

class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/v1/healthz")
async def healthz():
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START),
        "contexts_loaded": ctx_store.counts,
    }


@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "VERA Engine",
        "team_members": ["Sahil"],
        "model": "rule-based-deterministic-v1",
        "approach": "Priority-ranked decision engine + category-specific template composer with 20+ trigger handlers. Pure rule-based, no LLM dependency. Deterministic output guaranteed.",
        "contact_email": "sahil@example.com",
        "version": "1.0.0",
        "submitted_at": "2026-05-02T12:00:00Z",
    }


@app.post("/v1/context")
async def push_context(body: ContextBody):
    valid_scopes = {"category", "merchant", "customer", "trigger"}
    if body.scope not in valid_scopes:
        return {"accepted": False, "reason": "invalid_scope",
                "details": f"scope must be one of {valid_scopes}"}

    accepted, reason, cur_ver = ctx_store.push(
        body.scope, body.context_id, body.version, body.payload
    )

    if not accepted:
        resp = {"accepted": False, "reason": reason}
        if cur_ver is not None:
            resp["current_version"] = cur_ver
        return resp

    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.post("/v1/tick")
async def tick(body: TickBody):
    # Select best triggers to act on
    selections = select_triggers(
        body.available_triggers, ctx_store, conv_state, suppression, body.now
    )

    actions = []
    for sel in selections:
        trigger = sel["trigger"]
        merchant = sel["merchant"]
        category = sel["category"]
        customer = sel.get("customer")

        # Compose the message
        result = compose(category, merchant, trigger, customer)

        # Check anti-repetition
        conv_id = result["conversation_id"]
        if conv_state.is_body_repeated(conv_id, result["body"]):
            continue

        # Register the send
        sup_key = result["suppression_key"]
        suppression.suppress(sup_key, conv_id)
        conv_state.start_conversation(
            conv_id, result["merchant_id"], result.get("customer_id"),
            result["trigger_id"], result["body"]
        )

        actions.append(result)

    return {"actions": actions}


@app.post("/v1/reply")
async def reply(body: ReplyBody):
    # Record the incoming turn
    conv_state.add_turn(body.conversation_id, body.from_role, body.message)

    # Handle the reply
    result = handle_reply(
        body.conversation_id, body.message, conv_state, ctx_store
    )

    # If sending, check anti-repetition
    if result.get("action") == "send" and result.get("body"):
        if conv_state.is_body_repeated(body.conversation_id, result["body"]):
            result["body"] = result["body"] + " Let me know how you'd like to proceed."
        conv_state.add_turn(body.conversation_id, "vera", result["body"])

    # Track conversation status
    if result.get("action") == "end":
        conv_state.set_status(body.conversation_id, "ended")
    elif result.get("action") == "wait":
        conv_state.set_status(body.conversation_id, "waiting")

    return result
