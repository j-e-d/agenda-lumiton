"""Fetch pages with a real (headed) Chromium, for when Cloudflare blocks cloudscraper

Cloudflare challenges plain requests from datacenter IPs (GitHub runners,
VPSs) with a 403. A headed patchright Chromium gets the page directly;
headless Chromium is still challenged. On a machine without a display
(CI), run under `xvfb-run`.

Same small interface as a requests session (get/close), so the scraper can
swap it in for cloudscraper.
"""

import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack

CHALLENGE_TITLE = "just a moment"


class BrowserResponse:
    def __init__(self, url: str, status_code: int, text: str):
        self.url, self.status_code, self.text = url, status_code, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} Error for url: {self.url}")


def fetch(page, url: str, timeout: float, challenge_wait: float = 30) -> BrowserResponse:
    """Load url in page; if Cloudflare shows its challenge, give it time to
    clear itself and report the page it lands on"""
    response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
    if response is None:
        raise RuntimeError(f"No response loading {url}")
    status = response.status
    if CHALLENGE_TITLE in page.title().lower():
        deadline = time.monotonic() + challenge_wait
        while CHALLENGE_TITLE in page.title().lower() and time.monotonic() < deadline:
            time.sleep(1)
        if CHALLENGE_TITLE not in page.title().lower():
            # The challenge cleared itself and loaded the real page; its
            # status isn't exposed, only the challenge's (403)
            status = 200
        # else: still the challenge page, which the scraper reports as blocked
    return BrowserResponse(url, status, page.content())


class BrowserSession:
    def __init__(self):
        # Downloads Chromium on first use; a no-op once installed (cached in CI)
        subprocess.run([sys.executable, "-m", "patchright", "install", "--no-shell", "chromium"], check=True)

        from patchright.sync_api import sync_playwright

        # Undo whatever was set up if a later step fails
        with ExitStack() as stack:
            profile = stack.enter_context(tempfile.TemporaryDirectory())
            playwright = sync_playwright().start()
            stack.callback(playwright.stop)
            context = playwright.chromium.launch_persistent_context(profile, headless=False, no_viewport=True)
            stack.callback(context.close)
            self._page = context.pages[0] if context.pages else context.new_page()
            self._cleanup = stack.pop_all()

    def get(self, url: str, timeout: float = 30) -> BrowserResponse:
        return fetch(self._page, url, timeout)

    def close(self):
        self._cleanup.close()
