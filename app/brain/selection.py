"""Fail-closed selection gate. Browser, acquisition and core use separate clocks."""
from __future__ import annotations

import time
import uuid
import numpy as np
from .decoder import Decoder, DecoderConfig

LABELS = {"synthetic": "SYNTHETIC EEG — NO LIVE BRAIN INPUT",
          "replay": "RECORDED EEG REPLAY", "live_eeg": "LIVE EEG"}
TARGETS = {"planet.399", "planet.499", "planet.more_details", "navigation.back"}


class SelectionGate:
    def __init__(self, config=DecoderConfig(), source="synthetic", clock=time.monotonic):
        if source not in LABELS:
            raise ValueError("unknown source")
        self.decoder = Decoder(config)
        self.source, self.clock = source, clock
        self.context = None
        self.expires_at = 0.0
        self.sent = set()
        self.stop("not_configured")

    @staticmethod
    def key(context):
        return (context["input_session_id"], context["context_id"], context["revision"])

    def context_update(self, context):
        changed = self.context is None or self.key(context) != self.key(self.context)
        self.context = dict(context)
        self.expires_at = self.clock() + context["expires_in_ms"] / 1000
        if changed or not context["enabled"]:
            self.stop("context_changed")

    def stop(self, reason="stopped"):
        self.state, self.reason = "WAIT_RELEASE", reason
        self.decoder.reset()
        self.stimulus_at = None
        self.last_index = self.last_batch = None
        self.last_received = None
        self.sequence = -1
        self.frames = -1
        self.ready_at = float("inf")
        self.scores = None

    def configure(self, context, targets, frequencies):
        self.context_update(context)
        if (not context["enabled"] or len(targets) != 2 or len(set(targets)) != 2
                or not set(targets).issubset(TARGETS & set(context["allowed_targets"]))
                or len(frequencies) != 2 or not all(np.isfinite(f) and 8 <= f <= 18 for f in frequencies)
                or abs(frequencies[0] - frequencies[1]) < 2):
            raise ValueError("invalid selection configuration")
        self.stop("operator_rearm")
        self.targets, self.frequencies = tuple(targets), tuple(frequencies)
        self.state = "ARMED" if self.key(context) not in self.sent else "DECISION_SENT"

    def stimulus(self, message):
        if self.context is None or self.state != "ARMED":
            return
        if self.stimulus_at is not None and self.clock() - self.stimulus_at > 0.5:
            self.stop("stimulus_timeout")
            return
        valid = (message["context_id"] == self.context["context_id"]
                 and message["context_revision"] == self.context["revision"]
                 and all(message[k] for k in ("active", "visible", "focused"))
                 and message["sequence"] > self.sequence
                 and message["frame_count"] > self.frames
                 and message["dropped_frames"] == 0
                 and 0 <= message["largest_frame_gap_ms"] <= 35
                 and len(message["effective_frequencies_hz"]) == 2
                 and all(abs(a-b) < 0.2 for a, b in zip(message["effective_frequencies_hz"], self.frequencies)))
        if not valid:
            self.stop("invalid_stimulus")
            return
        if self.stimulus_at is None:
            self.ready_at = self.clock() + 0.5
        self.stimulus_at = self.clock()
        self.sequence, self.frames = message["sequence"], message["frame_count"]

    def active(self):
        now = self.clock()
        if self.state != "ARMED":
            return False
        if now >= self.expires_at or (self.stimulus_at is not None and now-self.stimulus_at > 0.5):
            self.stop("expired_context_or_stimulus")
            return False
        return self.stimulus_at is not None

    def feed(self, batch):
        now = self.clock()
        if not self.active() or now < self.ready_at:
            return None
        reason = self.decoder.quality(batch.samples_uv)
        if reason != "valid":
            self.stop(reason)
            return None
        if (batch.source != self.source or batch.sample_rate_hz != self.decoder.config.sample_rate_hz
                or not batch.valid or not 0 <= now-batch.received_at <= 0.5):
            reason = "source_rate_or_freshness"
        indices = batch.sample_indices
        if (len(indices) != batch.samples_uv.shape[1] or not len(indices)
                or not np.all(np.diff(indices) == 1)
                or (self.last_index is not None and indices[0] != self.last_index+1)
                or (self.last_batch is not None and batch.batch_id != self.last_batch+1)):
            reason = "gap"
        if reason != "valid":
            self.stop(reason)
            return None
        self.last_index, self.last_batch, self.last_received = indices[-1], batch.batch_id, batch.received_at
        decision = self.decoder.feed(batch.samples_uv, indices, self.frequencies)
        if decision is None:
            return None
        self.scores = decision["scores"]
        winner = decision["winner"]
        if winner is None:
            self.reason = "no_control_or_unstable"
            return None
        self.state = "DECISION_SENT"
        self.sent.add(self.key(self.context))
        start, end = self.decoder.indices[[0, -1]] / batch.sample_rate_hz * 1000
        return {"schema_version": 1, "event_id": str(uuid.uuid4()),
                "input_session_id": self.context["input_session_id"],
                "context_id": self.context["context_id"], "context_revision": self.context["revision"],
                "target_id": self.targets[winner], "source": self.source,
                "evidence": {"window_start_source_ms": float(start), "window_end_source_ms": float(end),
                             "sample_count": len(self.decoder.indices), "sample_rate_hz": batch.sample_rate_hz,
                             "winner_score": self.scores[winner], "runner_up_score": self.scores[1-winner],
                             "quality": "valid"}}

    def heartbeat(self):
        active = self.active()
        age = None if self.last_received is None else max(0, (self.clock()-self.last_received)*1000)
        return {"context_id": self.context["context_id"], "context_revision": self.context["revision"],
                "source_state": "ready" if active and age is not None and age <= 500 else "acquiring",
                "acquisition_age_ms": age, "stimulus_ready": active}
