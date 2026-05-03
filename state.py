"""
Context Store, Conversation State, and Suppression Manager.

All in-memory. Thread-safe for a single-process uvicorn worker.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ContextStore:
    """Version-controlled, idempotent context storage."""

    def __init__(self):
        # (scope, context_id) → {"version": int, "payload": dict}
        self._store: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._counts: Dict[str, int] = {
            "category": 0, "merchant": 0, "customer": 0, "trigger": 0
        }

    def push(self, scope: str, context_id: str, version: int, payload: dict) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Push context. Returns (accepted, reason_if_rejected, current_version_if_stale).
        Idempotent: same version = treated as stale (already have it).
        Higher version = replace.
        """
        if scope not in self._counts:
            return False, "invalid_scope", None

        key = (scope, context_id)
        existing = self._store.get(key)

        if existing and existing["version"] >= version:
            return False, "stale_version", existing["version"]

        is_new = key not in self._store
        self._store[key] = {"version": version, "payload": payload}

        if is_new:
            self._counts[scope] += 1

        return True, None, None

    def get(self, scope: str, context_id: str) -> Optional[dict]:
        """Get the payload for a given (scope, context_id)."""
        entry = self._store.get((scope, context_id))
        return entry["payload"] if entry else None

    def get_version(self, scope: str, context_id: str) -> Optional[int]:
        entry = self._store.get((scope, context_id))
        return entry["version"] if entry else None

    def get_all_by_scope(self, scope: str) -> Dict[str, dict]:
        """Return all payloads for a given scope as {context_id: payload}."""
        result = {}
        for (s, cid), entry in self._store.items():
            if s == scope:
                result[cid] = entry["payload"]
        return result

    @property
    def counts(self) -> Dict[str, int]:
        return dict(self._counts)


class ConversationState:
    """Track conversations in flight."""

    def __init__(self):
        # conversation_id → ConversationRecord
        self._conversations: Dict[str, Dict[str, Any]] = {}
        # Track sent bodies per conversation for anti-repetition
        self._sent_bodies: Dict[str, set] = {}

    def start_conversation(self, conversation_id: str, merchant_id: str,
                           customer_id: Optional[str], trigger_id: str,
                           first_body: str):
        self._conversations[conversation_id] = {
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "trigger_id": trigger_id,
            "status": "active",  # active, waiting, ended
            "turns": [{"from": "vera", "body": first_body, "ts": _now_iso()}],
            "auto_reply_count": 0,
            "created_at": _now_iso(),
        }
        self._sent_bodies.setdefault(conversation_id, set()).add(first_body.strip().lower())

    def add_turn(self, conversation_id: str, from_role: str, body: str):
        conv = self._conversations.get(conversation_id)
        if conv:
            conv["turns"].append({"from": from_role, "body": body, "ts": _now_iso()})
            if from_role == "vera":
                self._sent_bodies.setdefault(conversation_id, set()).add(body.strip().lower())

    def is_body_repeated(self, conversation_id: str, body: str) -> bool:
        return body.strip().lower() in self._sent_bodies.get(conversation_id, set())

    def get(self, conversation_id: str) -> Optional[Dict]:
        return self._conversations.get(conversation_id)

    def set_status(self, conversation_id: str, status: str):
        conv = self._conversations.get(conversation_id)
        if conv:
            conv["status"] = status

    def increment_auto_reply(self, conversation_id: str) -> int:
        conv = self._conversations.get(conversation_id)
        if conv:
            conv["auto_reply_count"] = conv.get("auto_reply_count", 0) + 1
            return conv["auto_reply_count"]
        return 0

    def get_auto_reply_count(self, conversation_id: str) -> int:
        conv = self._conversations.get(conversation_id)
        return conv.get("auto_reply_count", 0) if conv else 0

    def has_active_conversation(self, merchant_id: str) -> Optional[str]:
        """Return conversation_id if merchant has an active conversation."""
        for cid, conv in self._conversations.items():
            if conv["merchant_id"] == merchant_id and conv["status"] == "active":
                return cid
        return None

    def get_ended_merchants(self) -> set:
        """Return merchant_ids whose conversations ended (opted out)."""
        ended = set()
        for conv in self._conversations.values():
            if conv["status"] == "ended":
                ended.add(conv["merchant_id"])
        return ended


class SuppressionManager:
    """Prevent duplicate sends via suppression keys."""

    def __init__(self):
        self._keys: Dict[str, Dict[str, Any]] = {}  # key → {sent_at, conversation_id}

    def is_suppressed(self, key: str) -> bool:
        return key in self._keys

    def suppress(self, key: str, conversation_id: str):
        self._keys[key] = {
            "sent_at": _now_iso(),
            "conversation_id": conversation_id,
        }

    def clear(self, key: str):
        self._keys.pop(key, None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
