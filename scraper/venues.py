"""Venues scraped from Lumiton's agenda, shared by scraper and calendar generator"""

from typing import Optional

# Canonical venue name -> keyword identifying it in the site's venue text
VENUE_KEYWORDS = {
    "Lumiton": "lumiton",
    "Cine York": "york",
    "Centro Cultural Munro": "munro",
    "Quinta Trabucco": "trabucco",
    "Torre Ader": "torre ader",
}
VENUES = list(VENUE_KEYWORDS)


def normalize_venue(venue_text: str) -> Optional[str]:
    """Canonical venue name for the site's venue text, or None if unknown"""
    venue_lower = venue_text.lower()
    for venue, keyword in VENUE_KEYWORDS.items():
        if keyword in venue_lower:
            return venue
    return None


def venue_slug(venue: str) -> str:
    """File name stem for a venue's CSV/ICS: 'Cine York' -> 'cine_york'"""
    return venue.lower().replace(" ", "_")
