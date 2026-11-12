"""Venues scraped from Lumiton's agenda, shared by scraper and calendar generator"""

# Canonical venue name -> keyword identifying it in the site's venue text.
# Checked in this order: specific venue names come before "munro", which is
# also the locality of several venues (e.g. "Lumiton, Munro").
VENUE_KEYWORDS = {
    "Lumiton": "lumiton",
    "Cine York": "york",
    "Quinta Trabucco": "trabucco",
    "Torre Ader": "torre ader",
    "Centro Cultural Munro": "munro",
}
# Display/file order
VENUES = ["Lumiton", "Cine York", "Centro Cultural Munro", "Quinta Trabucco", "Torre Ader"]


def normalize_venue(venue_text: str) -> str | None:
    """Canonical venue name for the site's venue text, or None if unknown"""
    venue_lower = venue_text.lower()
    for venue, keyword in VENUE_KEYWORDS.items():
        if keyword in venue_lower:
            return venue
    return None


def venue_slug(venue: str) -> str:
    """File name stem for a venue's CSV/ICS: 'Cine York' -> 'cine_york'"""
    return venue.lower().replace(" ", "_")
