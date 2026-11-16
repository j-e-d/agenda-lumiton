import pytest

import browser_session
from browser_session import fetch
from scraper import is_challenge_page

CHALLENGE = "<html><title>Just a moment...</title></html>"
REAL = "<html><title>Agenda Presencial : Lumiton</title><article></article></html>"


class Resp:
    def __init__(self, status):
        self.status = status


class FakePage:
    """Shows each (title, html) in turn, one per title() poll; the last one stays"""

    def __init__(self, status, *states):
        self.status, self.states, self.polls = status, list(states), 0

    def goto(self, url, **kwargs):
        return None if self.status is None else Resp(self.status)

    def _state(self):
        return self.states[min(self.polls, len(self.states) - 1)]

    def title(self):
        title = self._state()[0]
        self.polls += 1
        return title

    def content(self):
        return self._state()[1]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(browser_session.time, "sleep", lambda s: None)


def test_real_page_is_returned_as_is():
    page = FakePage(200, ("Agenda Presencial : Lumiton", REAL))
    r = fetch(page, "https://lumiton.ar/", timeout=30)
    assert (r.status_code, r.text) == (200, REAL)


def test_waits_for_challenge_to_clear():
    page = FakePage(403, ("Just a moment...", CHALLENGE), ("Just a moment...", CHALLENGE), ("Agenda", REAL))
    r = fetch(page, "https://lumiton.ar/", timeout=30)
    r.raise_for_status()
    assert r.text == REAL


def test_challenge_that_never_clears_is_returned_as_blocked(monkeypatch):
    clock = iter(range(0, 1000, 10))
    monkeypatch.setattr(browser_session.time, "monotonic", lambda: next(clock))
    page = FakePage(403, ("Just a moment...", CHALLENGE))
    r = fetch(page, "https://lumiton.ar/", timeout=30, challenge_wait=30)
    assert r.status_code == 403
    assert is_challenge_page(r.text)


def test_no_response_is_an_error():
    with pytest.raises(RuntimeError, match="No response"):
        fetch(FakePage(None, ("", "")), "https://lumiton.ar/", timeout=30)


def test_http_error_status_is_kept():
    r = fetch(FakePage(500, ("Error", "<html>oops</html>")), "https://lumiton.ar/", timeout=30)
    with pytest.raises(RuntimeError, match="500"):
        r.raise_for_status()
