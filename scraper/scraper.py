#!/usr/bin/env python3
"""
Lumiton Agenda Scraper
Extracts film projection events from lumiton.ar/agenda-presencial/
"""

import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import cloudscraper
from bs4 import BeautifulSoup
import pytz

from event_keys import event_key
from imdb_dataset import IMDbDataset
from venues import VENUES, normalize_venue, venue_slug


class LumitonScraper:
    """Scrapes film events from Lumiton's agenda page"""

    BASE_URL = "https://lumiton.ar/agenda-presencial/"
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
        self.imdb = IMDbDataset()

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

    def _fetch_time_from_detail_page(self, url: str) -> Optional[str]:
        """Fetch event detail page and extract time if available

        Returns the time, "" if the page was read but shows no time, or None
        if the page could not be fetched (so a previously known time is kept).
        """
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

            return ""

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
                event["date"] = datetime.strptime(date_attr, "%Y-%m-%d").date().isoformat()
            except ValueError:
                print(f"Warning: Unexpected data-date format: {date_attr!r}")

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

        if not (event.get("title") and event.get("venue")):
            return None

        if not event.get("date"):
            print(f"Warning: Skipping '{event['title']}': no usable date")
            return None

        if not event.get("time") and event.get("url"):
            detail_time = self._fetch_time_from_detail_page(event["url"])
            if detail_time is not None:
                event["time"] = detail_time

        event["rating"] = ""
        event["duration"] = ""

        return event

    def _normalize_venue(self, venue_text: str) -> str:
        """Normalize venue name to standard format"""
        venue = normalize_venue(venue_text)
        if venue is None:
            print(f"Warning: Unknown venue '{venue_text}': its events only go to all_events "
                  f"(add it to scraper/venues.py for a per-venue calendar)")
            return venue_text
        return venue

    def scrape(self) -> List[Dict]:
        """Main scraping method"""
        print("Fetching page...")
        html = self.fetch_page()

        print("Parsing events...")
        self.events = self.parse_events(html)

        print(f"Found {len(self.events)} events")
        if not self.events:
            # A redesign or a challenge page parses to nothing; fail the run
            # instead of silently publishing stale calendars
            raise RuntimeError(f"No events parsed from {self.BASE_URL}; the page layout may have changed")
        return self.events

    def _load_existing_csv(self, filepath: Path) -> List[Dict]:
        """Load existing CSV rows

        Read errors are fatal: carrying on with an empty history would
        overwrite the CSV with only the fresh scrape.
        """
        if not filepath.exists():
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _merge(self, existing_rows: List[Dict], fresh_events: List[Dict]) -> List[Dict]:
        """Merge a fresh scrape into the existing rows

        Rows are grouped by event_key (URL, date, venue). Each group in the
        fresh scrape replaces that group's upcoming rows, so showings that
        were removed or retimed disappear instead of lingering as duplicates.
        Showings that already took place are kept even if the site stopped
        listing them. Groups not in the fresh scrape are kept as they are.

        Known values are carried over: a time the scrape couldn't determine
        (detail page unreachable) from the old row with the same time slot
        left over, and rating/duration from any row with the same URL.
        """
        now = datetime.now(self.TIMEZONE)
        known_imdb = {}
        for row in existing_rows:
            if row.get("url") and (row.get("rating") or row.get("duration")):
                known_imdb.setdefault(row["url"], row)

        fresh_groups: Dict[str, List[Dict]] = {}
        for event in fresh_events:
            fresh_groups.setdefault(event_key(event), []).append(event)
        existing_groups: Dict[str, List[Dict]] = {}
        for row in existing_rows:
            existing_groups.setdefault(event_key(row), []).append(row)

        replacements: Dict[str, List[Dict]] = {}
        for key, group in fresh_groups.items():
            old_group = existing_groups.get(key, [])
            fresh_times = {e["time"] for e in group if e.get("time")}
            unmatched_old = [r for r in old_group if r.get("time") not in fresh_times]

            for event in group:
                if "time" not in event and unmatched_old:
                    event["time"] = unmatched_old.pop(0).get("time", "")
                self._carry_over_fields(event, known_imdb.get(event.get("url")))
                self._enrich_with_imdb(event)

            # Old showings not in the fresh scrape: keep those that already happened
            kept_times = {e.get("time") for e in group}
            past = [r for r in old_group
                    if r.get("time") not in kept_times and self._has_started(r, now)]
            replacements[key] = past + group

        # Keep row order stable: a replaced group takes the place of its
        # first existing row; new groups are appended
        merged, placed = [], set()
        for row in existing_rows:
            key = event_key(row)
            if key not in replacements:
                merged.append(row)
            elif key not in placed:
                merged.extend(replacements[key])
                placed.add(key)
        for key, group in replacements.items():
            if key not in placed:
                merged.extend(group)
        return merged

    def _has_started(self, row: Dict, now: datetime) -> bool:
        """Whether a stored showing's start time has passed"""
        try:
            start = datetime.strptime(f"{row.get('date')} {row.get('time') or '23:59'}", "%Y-%m-%d %H:%M")
        except ValueError:
            return False
        return self.TIMEZONE.localize(start) <= now

    @staticmethod
    def _carry_over_fields(event: Dict, known: Optional[Dict]):
        """Reuse rating/duration already stored for the same URL (same film)"""
        if known and not (event.get("rating") or event.get("duration")):
            event["rating"] = known.get("rating", "")
            event["duration"] = known.get("duration", "")

    def _enrich_with_imdb(self, event: Dict) -> Dict:
        """Fill rating and duration from IMDb if either is missing

        Both values are taken from the same match, so a row never mixes the
        rating of one film with the runtime of another. Without a confident
        match, whatever was already known is kept.
        """
        if event.get("rating") and event.get("duration"):
            return event

        if not event.get("title"):
            return event

        imdb_data = self.imdb.get_movie_info(event["title"], event.get("description", ""))
        if imdb_data.get("rating") or imdb_data.get("duration"):
            event["rating"] = imdb_data["rating"]
            event["duration"] = imdb_data["duration"]

        return event

    def save_to_csv(self, output_dir: Path):
        """Save events to CSV files, preserving historical events"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not self.events:
            print("No events to save")
            return

        fieldnames = ["title", "date", "time", "venue", "url", "description", "rating", "duration"]

        combined_file = output_dir / "all_events.csv"
        existing_rows = self._load_existing_csv(combined_file)
        merged_events = self._merge(existing_rows, self.events)

        self._write_csv(combined_file, merged_events, fieldnames)
        print(f"Saved combined events to {combined_file} (total: {len(merged_events)}, scraped: {len(self.events)})")

        # Venue files are views of the combined file
        for venue in VENUES:
            venue_file = output_dir / f"{venue_slug(venue)}.csv"
            venue_events = [e for e in merged_events if e.get("venue") == venue]
            # Always rewrite, so a venue whose events are gone doesn't keep stale rows
            self._write_csv(venue_file, venue_events, fieldnames)
            print(f"Saved {venue} events to {venue_file} (total: {len(venue_events)})")

    def _write_csv(self, filepath: Path, events: List[Dict], fieldnames: List[str]):
        """Write events to CSV file with LF line endings, atomically"""
        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
        with open(tmp_path, "w", newline="\n", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(events)
        os.replace(tmp_path, filepath)


def main():
    """Main entry point"""
    scraper = LumitonScraper()

    scraper.scrape()

    data_dir = Path(__file__).parent.parent / "data"
    scraper.save_to_csv(data_dir)

    print("\nScraping completed successfully!")


if __name__ == "__main__":
    main()
