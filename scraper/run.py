#!/usr/bin/env python3
"""
Main script to run scraper and calendar generator
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from calendar_generator import CalendarGenerator
from imdb_dataset import normalize
from scraper import LumitonScraper


def write_unknown_venues(venues: set[str], path: Path):
    """Write "key<TAB>venue" lines for the workflow to report, or remove the
    file when there are none

    The key ignores case and accents, so spelling variants of one venue
    ('Teatro Colón', 'TEATRO COLON') are reported once.
    """
    by_key: dict[str, str] = {}
    for venue in sorted(venues):
        by_key.setdefault(normalize(venue), venue)
    if not by_key:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}\t{v}\n" for k, v in sorted(by_key.items())), encoding="utf-8")
    print(f"Unknown venues: {', '.join(by_key.values())}")


def main():
    """Run complete pipeline: scrape -> generate calendars"""
    print("=" * 60)
    print("Lumiton Agenda Scraper and Calendar Generator")
    print("=" * 60)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    calendars_dir = base_dir / "calendars"

    print("\n[1/2] Scraping events from lumiton.ar...")
    scraper = LumitonScraper()
    scraper.scrape()
    write_unknown_venues(scraper.unknown_venues, base_dir / ".cache" / "unknown_venues.txt")
    scraper.save_to_csv(data_dir)

    print("\n[2/2] Generating ICS calendar files...")
    generator = CalendarGenerator(data_dir, calendars_dir, base_dir / "docs")
    generator.generate_all()

    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)
    print(f"\nData saved to: {data_dir}")
    print(f"Calendars saved to: {calendars_dir}")


if __name__ == "__main__":
    main()
