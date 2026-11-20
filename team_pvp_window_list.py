"""List matching game windows so users can explicitly choose main/alt HWND.

Read-only helper; never guesses which account belongs to a window.
"""
import argparse
import json
import os


def list_candidates(provider, title):
    if not title or not title.strip():
        return {"status": "paused", "reason": "explicit_title_required", "windows": []}
    try:
        matches = provider.discover(title)
        windows = [
            {"hwnd": w.hwnd, "pid": w.pid, "title": w.title, "class_name": w.class_name}
            for w in matches
        ]
        if len(windows) != 2 or len({w["hwnd"] for w in windows}) != 2 or len({w["pid"] for w in windows}) != 2:
            return {"status": "paused", "reason": "exactly_two_distinct_windows_required", "windows": windows}
        return {"status": "choose_main_alt", "reason": "explicit_binding_required", "windows": windows}
    except Exception as exc:
        return {"status": "paused", "reason": "discovery_failed", "error_type": type(exc).__name__, "windows": []}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only HWND discovery for two logged-in game windows")
    parser.add_argument("--title", required=True, help="Case-insensitive substring of both game window titles")
    args = parser.parse_args(argv)
    if os.name != "nt":
        print(json.dumps({"status": "unsupported", "reason": "requires_windows"}))
        return 2
    from dpi_awareness import enable_per_monitor_dpi
    from windows_provider import WindowsClientProvider
    enable_per_monitor_dpi()
    result = list_candidates(WindowsClientProvider(), args.title)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "choose_main_alt":
        print("Choose the main and alt HWND yourself. This helper cannot identify which account is which.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
