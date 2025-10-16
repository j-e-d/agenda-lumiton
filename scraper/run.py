#!/usr/bin/env python3
"""
Main script to run scraper and calendar generator
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from scraper import LumitonScraper
from calendar_generator import CalendarGenerator


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
    scraper.save_to_csv(data_dir)

    print("\n[2/2] Generating ICS calendar files...")
    generator = CalendarGenerator(data_dir, calendars_dir)
    generator.generate_all()

    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)
    print(f"\nData saved to: {data_dir}")
    print(f"Calendars saved to: {calendars_dir}")


if __name__ == "__main__":
    main()
