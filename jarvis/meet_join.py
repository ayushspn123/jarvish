"""Standalone Google Meet joiner — runs as its OWN process.

Why a separate process: Playwright's sync API runs an event loop, and sharing a process with
the main app's async work (edge-tts) corrupts it. Running here in isolation keeps the app's
voice/interrupt working. This process stays alive to keep the meeting window open.

Usage (spawned by jarvis/tools/meet.py):
    python -m jarvis.meet_join <meet_url> <status_file> <profile_dir>
"""

from __future__ import annotations

import re
import sys
import time


def _write(status_file: str, text: str) -> None:
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def main() -> None:
    if len(sys.argv) < 4:
        return
    url, status_file, profile_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    # Optional 4th arg: which Chrome profile inside that dir to use (e.g. "Default").
    profile_directory = sys.argv[4] if len(sys.argv) > 4 else ""

    from playwright.sync_api import sync_playwright

    args = ["--use-fake-ui-for-media-stream", "--start-maximized"]
    if profile_directory:
        args.append(f"--profile-directory={profile_directory}")

    pw = sync_playwright().start()
    try:
        ctx = pw.chromium.launch_persistent_context(
            profile_dir,
            channel="chrome",
            headless=False,
            no_viewport=True,
            args=args,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="load", timeout=60000)

        # Meet's button is "Join now", or "Ask to join" / "Join anyway" depending on state.
        button = page.get_by_role(
            "button", name=re.compile(r"(Join now|Ask to join|Join anyway|Join)", re.I)
        ).first
        button.wait_for(timeout=45000)
        button.click()
        _write(status_file, "ok")

        # Stay alive so the meeting window stays open.
        while True:
            time.sleep(5)
    except Exception as exc:  # noqa: BLE001
        _write(status_file, "fail: " + (str(exc).splitlines()[0] if str(exc) else "unknown"))
        # Leave the window open a bit so the owner can sign in / click manually.
        time.sleep(120)
    finally:
        try:
            pw.stop()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
