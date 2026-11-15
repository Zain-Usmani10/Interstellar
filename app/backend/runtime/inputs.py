"""Shared input layer: sessions, the selection context, heartbeats and intent validation.

Mouse, keyboard and the optional EEG extension all propose selections through here. The only
capability is ``planet_explore``: an accepted intent changes which planet card is open and
nothing else. No code path from this module reaches the mission runtime or the transport.

There is one selection context for the app (screen, selected planet, revision). Every accepted
intent, from any source, increases the revision, so a late intent from another source is
rejected as stale. Each session has its own heartbeat and expiry.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
import uuid
from typing import Callable

from .events import EventHub

EEG_SOURCES = ("live_eeg", "replay", "synthetic")
ALL_SOURCES = ("mouse", "keyboard") + EEG_SOURCES
HEARTBEAT_MAX_AGE_S = 2.0
CONTEXT_TTL_S = 10.0
TARGETS = {"planet_choice": ["planet.399", "planet.499"],
           "planet_info": ["planet.more_details", "navigation.back"],
           "disabled": []}


class InputError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


class InputManager:
    def __init__(self, hub: EventHub, validators: dict, brain_enabled: bool,
                 clock: Callable[[], float] = time.monotonic):
        self.hub = hub
        self.validators = validators
        self.brain_enabled = brain_enabled
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}
        self.context_id = str(uuid.uuid4())
        self.revision = 0
        self.screen = "planet_choice"
        self.selected_body_id: str | None = None

    # ------------------------------------------------------------ sessions

    def register(self, source: str, adapter: dict) -> dict:
        if source not in ALL_SOURCES:
            raise InputError(422, "unknown_source")
        if source in EEG_SOURCES and not self.brain_enabled:
            raise InputError(403, "brain_disabled")      # BRAIN_ENABLED=false: core runs without it
        with self._lock:
            session_id = str(uuid.uuid4())
            session = {"id": session_id, "token": secrets.token_urlsafe(24), "source": source,
                       "adapter": adapter, "heartbeat_at": None, "heartbeat": None,
                       "expires_at": self._clock() + CONTEXT_TTL_S, "events": {}}
            self._sessions[session_id] = session
            return {"input_session_id": session_id, "token": session["token"],
                    "capability": "planet_explore", "context": self._context(session)}

    def authenticate(self, session_id: str | None, token: str | None) -> dict:
        """Find the session for a token. The token is valid only for input routes."""
        with self._lock:
            for session in self._sessions.values():
                if token and secrets.compare_digest(session["token"], token) and session_id in (None, session["id"]):
                    return session
        raise InputError(401, "invalid_input_token")

    def owns_token(self, token: str | None) -> bool:
        return bool(token) and any(s["token"] == token for s in self._sessions.values())

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    # ------------------------------------------------------------ context

    def _fresh(self, session: dict) -> bool:
        """EEG-type sources must keep heartbeating; mouse/keyboard are direct operator actions."""
        if session["source"] not in EEG_SOURCES:
            return True
        at = session["heartbeat_at"]
        return at is not None and self._clock() - at <= HEARTBEAT_MAX_AGE_S

    def _context(self, session: dict) -> dict:
        remaining = max(0.0, session["expires_at"] - self._clock())
        if session["source"] not in EEG_SOURCES:
            remaining = CONTEXT_TTL_S
        return {"schema_version": 1, "context_id": self.context_id, "revision": self.revision,
                "input_session_id": session["id"], "capability": "planet_explore",
                "screen": self.screen, "selected_body_id": self.selected_body_id,
                "allowed_targets": list(TARGETS[self.screen]),
                "enabled": self.screen != "disabled", "expires_in_ms": int(remaining * 1000)}

    def context(self, session: dict) -> dict:
        with self._lock:
            return self._context(session)

    def heartbeat(self, session: dict, body: dict) -> dict:
        if not self.validators["input_heartbeat"].is_valid(body):
            raise InputError(422, "invalid_schema")
        with self._lock:
            now = self._clock()
            if now > session["expires_at"]:
                # The context lapsed with nobody attending it: force fresh evidence.
                self._bump("context_expired")
            session["heartbeat_at"], session["heartbeat"] = now, body
            session["expires_at"] = now + CONTEXT_TTL_S       # renewal does not change the revision
            return self._context(session)

    def _bump(self, source: str, event_id: str | None = None) -> None:
        self.revision += 1
        self.hub.publish("selection", {"selected_body_id": self.selected_body_id, "screen": self.screen,
                                       "context_revision": self.revision, "source": source,
                                       "event_id": event_id})

    def bump(self, reason: str) -> None:
        """Mission state changed or the link reconnected: old evidence must not carry over."""
        with self._lock:
            self._bump(reason)

    def state(self) -> dict:
        with self._lock:
            return {"selected_body_id": self.selected_body_id, "screen": self.screen,
                    "context_id": self.context_id, "context_revision": self.revision}

    # ------------------------------------------------------------ intents

    def submit(self, session: dict, intent: dict) -> dict:
        """Validate one SelectionIntent and apply it if every check passes."""
        with self._lock:
            def result(reason: str) -> dict:
                return {"event_id": intent.get("event_id") if isinstance(intent, dict) else None,
                        "accepted": reason == "accepted", "reason": reason,
                        "new_context_revision": self.revision}

            if not self.validators["selection_intent"].is_valid(intent):
                return result("invalid_schema")
            if session["id"] not in self._sessions or intent["input_session_id"] != session["id"]:
                return result("inactive_session")
            if intent["source"] != session["source"]:
                return result("source_mismatch")
            # Exact retry returns the first answer; the same id with other content is a conflict.
            canonical = json.dumps(intent, sort_keys=True)
            if intent["event_id"] in session["events"]:
                seen, first = session["events"][intent["event_id"]]
                return first if seen == canonical else result("duplicate_event_conflict")

            answer = result(self._check(session, intent))
            if answer["accepted"]:
                self._apply(intent)
                answer["new_context_revision"] = self.revision
            session["events"][intent["event_id"]] = (canonical, answer)
            return answer

    def _check(self, session: dict, intent: dict) -> str:
        eeg = session["source"] in EEG_SOURCES
        if self.screen == "disabled":
            return "input_disabled"
        if eeg and not self._fresh(session):
            return "stale_heartbeat"
        if eeg and self._clock() > session["expires_at"]:
            return "expired_context"
        if intent["context_id"] != self.context_id or intent["context_revision"] != self.revision:
            return "stale_context"
        if eeg:
            beat = session["heartbeat"]
            attested = (beat["context_id"] == self.context_id and beat["context_revision"] == self.revision
                        and beat["source_state"] == "ready" and beat["stimulus_ready"])
            if not attested:                         # the source has not confirmed it is on this context
                return "stale_heartbeat"
            if intent["evidence"]["quality"] != "valid":
                return "invalid_quality"
        if intent["target_id"] not in TARGETS[self.screen]:
            return "action_unavailable"
        return "accepted"

    def _apply(self, intent: dict) -> None:
        target = intent["target_id"]
        if target.startswith("planet.") and target != "planet.more_details":
            self.selected_body_id, self.screen = target.split(".")[1], "planet_info"
        elif target == "navigation.back":
            self.selected_body_id, self.screen = None, "planet_choice"
        self._bump(intent["source"], intent["event_id"])
