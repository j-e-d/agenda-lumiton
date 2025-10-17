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

import cloudscraper
from bs4 import BeautifulSoup
import pytz


class LumitonScraper:
    """Scrapes film events from Lumiton's agenda page"""

    BASE_URL = "https://lumiton.ar/agenda-presencial/"
    VENUES = ["Lumiton", "Cine York", "Centro Cultural Munro"]
    TIMEZONE = pytz.timezone("America/Argentina/Buenos_Aires")

    def __init__(self):
        self.events = []
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )

    def fetch_page(self) -> str:
        """Fetch the HTML content of the agenda page"""
        try:
            response = self.scraper.get(self.BASE_URL, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
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

    def _fetch_time_from_detail_page(self, url: str) -> str:
        """Fetch event detail page and extract time if available"""
        if not url:
            return None

        try:
            if url.startswith("/"):
                url = "https://lumiton.ar" + url

            print(f"Fetching time from detail page: {url}")
            response = self.scraper.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            hora_elem = soup.find(class_="g-event-hora")
            if hora_elem:
                time_text = hora_elem.get_text(strip=True)
                time_match = re.search(r"(\d{1,2}:\d{2})", time_text)
                if time_match:
                    return time_match.group(1)

        except Exception as e:
            print(f"Warning: Could not fetch time from detail page {url}: {e}")

        return None

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

        fecha_elem = item.find(class_="g-event-fecha")
        if fecha_elem:
            fecha_text = fecha_elem.get_text(strip=True)
            time_match = re.search(r"(\d{1,2}:\d{2})", fecha_text)
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

        if not event.get("time") and event.get("url"):
            detail_time = self._fetch_time_from_detail_page(event["url"])
            if detail_time:
                event["time"] = detail_time

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

    def _create_event_id(self, event: Dict) -> str:
        """Create unique event ID based on date, time, and venue"""
        date = event.get("date", "")
        time = event.get("time", "")
        venue = event.get("venue", "")
        return f"{date}|{time}|{venue}"

    def _load_existing_csv(self, filepath: Path, fieldnames: List[str]) -> Dict[str, Dict]:
        """Load existing CSV data into a dictionary keyed by event ID"""
        existing_events = {}
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        event_id = self._create_event_id(row)
                        existing_events[event_id] = row
            except Exception as e:
                print(f"Warning: Could not load existing CSV {filepath}: {e}")
        return existing_events

    def save_to_csv(self, output_dir: Path):
        """Save events to CSV files, preserving historical events"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not self.events:
            print("No events to save")
            return

        fieldnames = ["title", "date", "time", "venue", "url", "description"]

        combined_file = output_dir / "all_events.csv"
        existing_events = self._load_existing_csv(combined_file, fieldnames)

        for event in self.events:
            event_id = self._create_event_id(event)
            existing_events[event_id] = event

        merged_events = list(existing_events.values())
        self._write_csv(combined_file, merged_events, fieldnames)
        print(f"Saved combined events to {combined_file} (total: {len(merged_events)}, new: {len(self.events)})")

        for venue in self.VENUES:
            venue_file = output_dir / f"{venue.lower().replace(' ', '_')}.csv"
            existing_venue_events = self._load_existing_csv(venue_file, fieldnames)

            new_venue_events = [e for e in self.events if e.get("venue") == venue]
            for event in new_venue_events:
                event_id = self._create_event_id(event)
                existing_venue_events[event_id] = event

            merged_venue_events = list(existing_venue_events.values())
            if merged_venue_events:
                self._write_csv(venue_file, merged_venue_events, fieldnames)
                print(f"Saved {venue} events to {venue_file} (total: {len(merged_venue_events)}, new: {len(new_venue_events)})")

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
