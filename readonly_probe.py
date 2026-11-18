"""Opt-in Windows read-only probe; captures are never saved or interpreted as game states."""
import argparse
import json
import os


def probe(provider, title_filter):
    if not title_filter or not title_filter.strip():
        raise ValueError('nonempty title filter required')
    candidates = provider.discover(title_filter)
    if len(candidates) != 2:
        return {'mode': 'read_only', 'status': 'paused', 'reason': 'exactly_two_windows_required', 'count': len(candidates)}
    if len({w.hwnd for w in candidates}) != 2 or len({w.pid for w in candidates}) != 2:
        return {'mode': 'read_only', 'status': 'paused', 'reason': 'ambiguous_window_identity'}
    results = []
    provider_boundaries = []
    for item in candidates:
        try:
            bound = provider.bind(item.hwnd)
            before = provider.client_rect(item.hwnd)
            frame1 = provider.screenshot(item.hwnd) if before else None
            middle = provider.client_rect(item.hwnd)
            frame2 = provider.screenshot(item.hwnd) if middle == before and frame1 else None
            after = provider.client_rect(item.hwnd)
            # Recheck OS identity after both captures: HWND reuse, PID/title/class
            # changes must never be reported as a safe, stable binding.
            final_identity = provider.identity(item.hwnd)
            valid = (bound == item and final_identity == item and before is not None and before == middle == after
                     and bool(frame1) and bool(frame2))
            provider_boundaries.append(before)
            results.append({'handle': item.hwnd, 'pid': item.pid, 'capture_ok': valid,
                            'client_size': [before.width, before.height] if before else None})
        except Exception:
            provider_boundaries.append(None)
            results.append({'handle': item.hwnd, 'pid': item.pid, 'capture_ok': False, 'client_size': None})
    # A window verified earlier may be replaced while the other is captured.
    # Revalidate BOTH identities and bounds before reporting the pair as ready.
    for index, item in enumerate(candidates):
        try:
            if (provider.identity(item.hwnd) != item or
                    provider.client_rect(item.hwnd) != provider_boundaries[index]):
                results[index]['capture_ok'] = False
        except Exception:
            results[index]['capture_ok'] = False
    return {'mode': 'read_only', 'status': 'capture_ready_not_game_verified' if all(r['capture_ok'] for r in results) else 'paused',
            'windows': results, 'game_state_verified': False, 'input_enabled': False}


def main():
    parser = argparse.ArgumentParser(description='Windows read-only window/capture health probe; no clicks')
    parser.add_argument('--title', required=True, help='Window title substring')
    args = parser.parse_args()
    if os.name != 'nt':
        print(json.dumps({'status': 'unsupported', 'reason': 'requires_windows'}))
        return 2
    from windows_provider import WindowsClientProvider
    print(json.dumps(probe(WindowsClientProvider(), args.title), ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
