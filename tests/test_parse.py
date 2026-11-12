import pytest

from conftest import FIXTURES
from scraper import FetchError, is_challenge_page


def parse(scraper):
    return scraper.parse_events((FIXTURES / "agenda.html").read_text(encoding="utf-8"))


def test_parses_saved_agenda_page(scraper):
    events = {e["title"]: e for e in parse(scraper)}
    assert set(events) >= {"LABERINTO", "MI VECINO TOTORO", "2001: ODISEA EN EL ESPACIO"}

    laberinto = events["LABERINTO"]
    assert laberinto["date"] == "2026-11-22"
    assert laberinto["time"] == "16:00"
    assert laberinto["venue"] == "Cine York"
    assert laberinto["url"].startswith("https://lumiton.ar/evento/")
    assert events["MI VECINO TOTORO"]["venue"] == "Centro Cultural Munro"


def test_descriptions_keep_word_spacing(scraper):
    # Inline markup used to glue words together ("35 mmCuando")
    html = (
        (FIXTURES / "agenda.html")
        .read_text(encoding="utf-8")
        .replace("Sinopsis: Sarah", "En 35 mm<br><strong>Cuando</strong>\n\n  Sarah")
    )
    laberinto = next(e for e in scraper.parse_events(html) if e["title"] == "LABERINTO")
    assert laberinto["description"].startswith("En 35 mm Cuando Sarah ")


def test_untimed_event_asks_detail_page(scraper):
    html = (FIXTURES / "agenda.html").read_text(encoding="utf-8").replace("16:00hs", "")
    asked = []
    scraper._fetch_time_from_detail_page = lambda url: asked.append(url) or "19:15"
    laberinto = next(e for e in scraper.parse_events(html) if e["title"] == "LABERINTO")
    assert laberinto["time"] == "19:15"
    assert asked == [laberinto["url"]]


def test_page_without_events_fails_at_once(scraper):
    # Not a challenge page, so most likely a redesign: no retry
    scraper.fetch_page = lambda: "<html><body><p>Agenda renovada</p></body></html>"
    with pytest.raises(RuntimeError, match="No events parsed"):
        scraper.scrape()
    assert scraper.waits == []


def fetches(*results):
    """fetch_page stub returning or raising each result in turn"""
    pending = iter(results)

    def fetch():
        result = next(pending)
        if isinstance(result, Exception):
            raise result
        return result

    return fetch


def test_blocked_fetch_is_retried_with_a_new_session(scraper):
    page = (FIXTURES / "agenda.html").read_text(encoding="utf-8")
    scraper.fetch_page = fetches(FetchError("403 Client Error: Forbidden"), page)
    assert len(scraper.scrape()) == 4
    assert scraper.waits == list(scraper.RETRY_DELAYS)
    assert len(scraper.sessions) == 2
    assert scraper.sessions[0].closed
    assert scraper.scraper is scraper.sessions[1]


def test_persistent_block_raises_after_retries(scraper):
    blocked = [FetchError("403 Client Error: Forbidden")] * (len(scraper.RETRY_DELAYS) + 1)
    scraper.fetch_page = fetches(*blocked)
    with pytest.raises(FetchError, match="403"):
        scraper.scrape()
    assert scraper.waits == list(scraper.RETRY_DELAYS)
    assert len(scraper.sessions) == len(scraper.RETRY_DELAYS) + 1


def test_other_errors_are_not_retried(scraper):
    scraper.fetch_page = fetches(TypeError("bug"))
    with pytest.raises(TypeError):
        scraper.scrape()
    assert scraper.waits == []


class Response:
    def __init__(self, text, status=200):
        self.text, self.status = text, status

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"{self.status} Client Error")


@pytest.mark.parametrize(
    "response, message",
    [
        (Response("<html><title>Just a moment...</title></html>"), "challenge"),
        (Response("Forbidden", 403), "403"),
    ],
)
def test_fetch_page_reports_blocks_as_fetch_errors(scraper, response, message):
    scraper.scraper.get = lambda *a, **k: response
    with pytest.raises(FetchError, match=message):
        scraper.fetch_page()


def test_fetch_page_returns_real_page(scraper):
    page = (FIXTURES / "agenda.html").read_text(encoding="utf-8")
    assert not is_challenge_page(page)
    scraper.scraper.get = lambda *a, **k: Response(page)
    assert scraper.fetch_page() == page
