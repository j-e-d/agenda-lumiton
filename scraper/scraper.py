#!/usr/bin/env python3
"""
Lumiton Agenda Scraper
Extracts film projection events from lumiton.ar/agenda-presencial/
"""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
import pytz


class LumitonScraper:
    """Scrapes film events from Lumiton's agenda page"""

    BASE_URL = "https://lumiton.ar/agenda-presencial/"
    VENUES = ["Lumiton", "Cine York", "Centro Cultural Munro"]
    TIMEZONE = pytz.timezone("America/Argentina/Buenos_Aires")

    def __init__(self):
        self.events = []

    def fetch_page(self) -> str:
        """Fetch the HTML content of the agenda page"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
        try:
            response = requests.get(self.BASE_URL, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch page: {e}")

    def parse_events(self, html: str) -> List[Dict]:
        """Parse HTML and extract event information"""
        soup = BeautifulSoup(html, "html.parser")
        events = []

        event_items = soup.find_all("article") or soup.find_all(
            "div", class_=re.compile(r"event|film|agenda|post")
        )

        for item in event_items:
            try:
                event = self._extract_event_data(item)
                if event:
                    events.append(event)
            except Exception as e:
                print(f"Warning: Failed to parse event: {e}")
                continue

        return events

    def _extract_event_data(self, item) -> Dict:
        """Extract individual event data from HTML element"""
        event = {}

        title_elem = item.find("h3")
        if title_elem:
            event["title"] = title_elem.get_text(strip=True)

        date_attr = item.get("data-date")
        if date_attr:
            try:
                dt = datetime.strptime(date_attr, "%Y-%m-%d")
                event["date"] = f"{dt.day}/{dt.month}"
            except:
                pass

        time_elem = item.find(class_="g-event-fecha")
        if time_elem:
            time_text = time_elem.get_text()
            time_match = re.search(r"(\d{1,2}:\d{2})\s*hs", time_text)
            if time_match:
                event["time"] = time_match.group(1)

        venue_elem = item.find("span", class_="font-semibold")
        if venue_elem:
            venue_text = venue_elem.get_text(strip=True)
            event["venue"] = self._normalize_venue(venue_text)

        link_elem = item.find("a", href=True)
        if link_elem:
            event["url"] = link_elem["href"]

        desc_elem = item.find("p", class_="line-clamp-3")
        if desc_elem:
            event["description"] = desc_elem.get_text(strip=True)

        if event.get("title") and event.get("venue"):
            return event

        return None

    def _parse_datetime(self, text: str) -> Dict:
        """Parse date and time from text"""
        result = {}

        date_match = re.search(r"\d{1,2}/\d{1,2}", text)
        if date_match:
            result["date"] = date_match.group()

        time_match = re.search(r"\d{1,2}:\d{2}", text)
        if time_match:
            result["time"] = time_match.group()

        return result

    def _normalize_venue(self, venue_text: str) -> str:
        """Normalize venue name to standard format"""
        venue_lower = venue_text.lower()

        if "york" in venue_lower:
            return "Cine York"
        elif "munro" in venue_lower:
            return "Centro Cultural Munro"
        elif "lumiton" in venue_lower:
            return "Lumiton"

        return venue_text

    def scrape(self) -> List[Dict]:
        """Main scraping method"""
        print("Fetching page...")
        html = self.fetch_page()

        print("Parsing events...")
        self.events = self.parse_events(html)

        print(f"Found {len(self.events)} events")
        return self.events

    def save_to_csv(self, output_dir: Path):
        """Save events to CSV files"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not self.events:
            print("No events to save")
            return

        fieldnames = ["title", "date", "time", "venue", "url", "description"]

        combined_file = output_dir / "all_events.csv"
        self._write_csv(combined_file, self.events, fieldnames)
        print(f"Saved combined events to {combined_file}")

        for venue in self.VENUES:
            venue_events = [e for e in self.events if e.get("venue") == venue]
            if venue_events:
                venue_file = output_dir / f"{venue.lower().replace(' ', '_')}.csv"
                self._write_csv(venue_file, venue_events, fieldnames)
                print(f"Saved {len(venue_events)} events to {venue_file}")

    def _write_csv(self, filepath: Path, events: List[Dict], fieldnames: List[str]):
        """Write events to CSV file with LF line endings"""
        with open(filepath, "w", newline="\n", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(events)


def main():
    """Main entry point"""
    scraper = LumitonScraper()

    scraper.scrape()

    data_dir = Path(__file__).parent.parent / "data"
    scraper.save_to_csv(data_dir)

    print("\nScraping completed successfully!")


if __name__ == "__main__":
    main()
