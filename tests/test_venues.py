import pytest

from conftest import FIXTURES
from venues import VENUES, normalize_venue, venue_slug


@pytest.mark.parametrize(
    "text, venue",
    [
        ("Lumiton", "Lumiton"),
        ("CINE YORK", "Cine York"),
        ("Centro Cultural Munro", "Centro Cultural Munro"),
        ("Quinta Trabucco", "Quinta Trabucco"),
        ("Torre Ader", "Torre Ader"),
        # "Munro" is also a locality: the specific venue name wins
        ("Lumiton, Munro", "Lumiton"),
        ("Torre Ader (Munro)", "Torre Ader"),
    ],
)
def test_normalize_venue(text, venue):
    assert normalize_venue(text) == venue


def test_unknown_venue():
    assert normalize_venue("Teatro Colón") is None


def test_slugs_match_published_files():
    assert [venue_slug(v) for v in VENUES] == [
        "lumiton",
        "cine_york",
        "centro_cultural_munro",
        "quinta_trabucco",
        "torre_ader",
    ]


def test_scraper_records_unknown_venues_of_kept_events(scraper):
    page = (FIXTURES / "agenda.html").read_text(encoding="utf-8")
    # The first event (LABERINTO, Cine York) at an unknown venue: reported
    scraper.parse_events(page.replace(">Cine York<", ">Teatro Colón<", 1))
    # Same event dropped for having no usable date: not reported
    dropped = page.replace(">Cine York<", ">Teatro Dropped<", 1).replace('data-date="2026-11-22"', 'data-date="bad"', 1)
    scraper.parse_events(dropped)
    assert scraper.unknown_venues == {"Teatro Colón"}


def test_unknown_venues_file(tmp_path):
    from run import write_unknown_venues

    path = tmp_path / ".cache" / "unknown_venues.txt"
    write_unknown_venues({"Teatro Colón", "TEATRO COLON", "Casa B"}, path)
    assert path.read_text(encoding="utf-8") == "casa b\tCasa B\nteatro colon\tTEATRO COLON\n"
    write_unknown_venues(set(), path)
    assert not path.exists()
