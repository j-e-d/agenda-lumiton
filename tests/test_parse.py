from conftest import FIXTURES


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


def test_empty_page_fails_the_run(scraper):
    import pytest

    scraper.fetch_page = lambda: "<html><body>Just a moment...</body></html>"
    with pytest.raises(RuntimeError):
        scraper.scrape()
