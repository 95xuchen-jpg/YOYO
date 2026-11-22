"""Offline replay of the advisory-only Fruit Troupe evidence sequence.

JSONL format: one FruitEvidence object per line. No game input or credentials.
"""
import json
from dataclasses import fields
from pathlib import Path

from fruit_sequence_gate import FruitEvidence, FruitSequenceGate


_ALLOWED = {f.name for f in fields(FruitEvidence)}


def replay_jsonl(path):
    """Return a fail-closed report from a local, explicitly selected recording."""
    gate = FruitSequenceGate()
    decisions = []
    source = Path(path)
    with source.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict) or set(raw) != _ALLOWED:
                    raise ValueError("evidence_schema_mismatch")
                if any(type(raw[name]) is not bool for name in (
                    "main_stable", "alt_stable", "same_room_verified",
                    "same_instance_verified", "main_reward_specific",
                    "alt_reward_specific"
                )):
                    raise ValueError("invalid_boolean")
                if any(not isinstance(raw[name], str) for name in ("main_state", "alt_state")):
                    raise ValueError("invalid_state")
                item = FruitEvidence(**raw)
                decision = gate.advance(item)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                return {"status": "paused", "reason": "invalid_evidence",
                        "line": line_number, "details": str(exc),
                        "decisions": decisions, "input_enabled": False}
            decisions.append({"line": line_number, **decision})
            if decision["status"] == "paused":
                return {"status": "paused", "reason": decision["reason"],
                        "line": line_number, "decisions": decisions,
                        "input_enabled": False}
    if not decisions:
        return {"status": "paused", "reason": "empty_evidence",
                "decisions": [], "input_enabled": False}
    return {"status": decisions[-1]["status"], "reason": decisions[-1]["reason"],
            "decisions": decisions, "input_enabled": False}
