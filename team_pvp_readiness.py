"""Dual-account team-PVP readiness monitor (read-only, no input injection).

Requires two already logged-in game windows. User must explicitly assign HWNDs.
Never claims that opaque screenshots prove a match, result, or account identity.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone

from observation_bridge import capture_pair


def inspect(provider, title, main_hwnd, alt_hwnd):
    if not title or not title.strip():
        return {"status": "paused", "reason": "explicit_title_required"}
    if not all(type(x) is int and x > 0 for x in (main_hwnd, alt_hwnd)) or main_hwnd == alt_hwnd:
        return {"status": "paused", "reason": "explicit_distinct_hwnds_required"}
    try:
        windows = provider.discover(title)
        if len(windows) != 2 or len({w.hwnd for w in windows}) != 2 or len({w.pid for w in windows}) != 2:
            raise ValueError("exactly_two_distinct_windows_required")
        by_hwnd = {w.hwnd: w for w in windows}
        if set(by_hwnd) != {main_hwnd, alt_hwnd}:
            raise ValueError("window_binding_mismatch")
        bindings = []
        for account, hwnd in (("main", main_hwnd), ("alt", alt_hwnd)):
            identity = by_hwnd[hwnd]
            if provider.bind(hwnd) != identity:
                raise ValueError("window_identity_changed")
            bindings.append((account, hwnd, identity.pid))
        evidence = capture_pair(provider, tuple(bindings))
        # Never accept capture evidence assigned to the wrong account or window.
        expected = {(account, hwnd, pid) for account, hwnd, pid in bindings}
        observed = {(e.account_id, e.hwnd, e.pid) for e in evidence}
        if len(evidence) != 2 or observed != expected:
            return {"status": "paused", "reason": "capture_binding_mismatch"}
        # Revalidate both HWND/PID identities *after* the two-frame capture.
        # Windows may recycle a handle or a client may restart during capture.
        # A pre-capture bind alone cannot establish post-capture stability.
        for account, hwnd, pid in bindings:
            if provider.bind(hwnd) != by_hwnd[hwnd]:
                return {"status": "paused", "reason": "window_identity_changed_during_capture"}
        refreshed = provider.discover(title)
        if (len(refreshed) != 2 or
                {w.hwnd: w for w in refreshed} != by_hwnd):
            return {"status": "paused", "reason": "window_set_changed_during_capture"}
        if not all(e.identity_ok and e.geometry_ok and e.two_frames_present for e in evidence):
            return {"status": "paused", "reason": "capture_or_identity_unstable",
                    "windows": [e.__dict__ for e in evidence]}
        return {"status": "capture_ready", "reason": "game_state_unverified",
                "windows": [e.__dict__ for e in evidence]}
    except Exception as exc:
        return {"status": "paused", "reason": "preflight_failed",
                "error_type": type(exc).__name__}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Team PVP dual-window read-only readiness monitor")
    parser.add_argument("--title", required=True, help="Game window title substring")
    parser.add_argument("--main-hwnd", type=int, required=True)
    parser.add_argument("--alt-hwnd", type=int, required=True)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--max-checks", type=int, default=120)
    parser.add_argument("--log", default="team_pvp_readiness.jsonl")
    args = parser.parse_args(argv)
    if args.interval < 0.5 or not 1 <= args.max_checks <= 1200:
        parser.error("interval must be >=0.5 and max-checks between 1 and 1200")
    if os.name != "nt":
        print(json.dumps({"status": "unsupported", "reason": "requires_windows"}))
        return 2
    from dpi_awareness import enable_per_monitor_dpi
    from windows_provider import WindowsClientProvider
    enable_per_monitor_dpi()
    provider = WindowsClientProvider()
    print("READ ONLY. Ctrl+C stops. No matchmaking, battles, clicks or rewards.")
    try:
        with open(args.log, "a", encoding="utf-8") as logfile:
            for i in range(args.max_checks):
                result = inspect(provider, args.title, args.main_hwnd, args.alt_hwnd)
                event = {"timestamp": datetime.now(timezone.utc).isoformat(),
                         "check": i + 1, "mode": "read_only", "input_enabled": False,
                         "game_state_verified": False, **result}
                logfile.write(json.dumps(event, ensure_ascii=False) + "\n")
                logfile.flush()
                print(json.dumps(event, ensure_ascii=False))
                if result["status"] != "capture_ready":
                    return 2
                if i + 1 < args.max_checks:
                    time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped by user")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
