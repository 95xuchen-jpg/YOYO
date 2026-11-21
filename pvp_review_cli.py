"""Offline team-PVP evidence review CLI. Never interacts with the game.

Usage: python pvp_review_cli.py evidence.json
The JSON must contain two records with account, hwnd, pid, phase,
frame_hashes, session_id and reviewed fields.
"""
import argparse
import json
import sys
from pathlib import Path
from pvp_evidence_gate import Evidence, Phase, inspect_pair


def review_payload(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        return {"status": "paused", "reason": "invalid_payload", "input_enabled": False}
    try:
        records = [
            Evidence(
                account=item["account"], hwnd=item["hwnd"], pid=item["pid"],
                phase=Phase(item["phase"]), frame_hashes=tuple(item["frame_hashes"]),
                session_id=item["session_id"], reviewed=item.get("reviewed", False)
            )
            for item in payload["records"]
        ]
    except (KeyError, TypeError, ValueError):
        return {"status": "paused", "reason": "invalid_record", "input_enabled": False}
    return inspect_pair(records)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline-only PVP evidence review; no game input")
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = review_payload(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result = {"status": "paused", "reason": "evidence_read_error",
                  "detail": type(exc).__name__, "input_enabled": False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "observed" else 2


if __name__ == "__main__":
    sys.exit(main())
