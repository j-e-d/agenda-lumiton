import pytest

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
