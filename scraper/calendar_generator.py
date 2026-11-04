#!/usr/bin/env python3
"""
Calendar Generator
Converts CSV event data to ICS calendar files
"""

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from icalendar import Calendar, Event
import pytz

from event_keys import event_key, keyed_events
from venues import VENUES, venue_slug


class CalendarGenerator:
    """Generates ICS calendar files from CSV event data"""

    TIMEZONE = pytz.timezone("America/Argentina/Buenos_Aires")
    CALENDAR_RETENTION_DAYS = 30
    DEFAULT_TIME = "20:00"  # only used to place untimed events for date filtering
    NO_TIME_NOTE = "(confirmar horario)"
    HASH_PROP = "X-LUMITON-HASH"
    HASHED_FIELDS = ("title", "date", "time", "venue", "url", "description", "rating", "duration")

    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_stamp = datetime.now(pytz.UTC).replace(microsecond=0)

    def read_csv(self, filepath: Path) -> List[Dict]:
        """Read events from CSV file"""
        events = []

        if not filepath.exists():
            print(f"Warning: {filepath} does not exist")
            return events

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            events = list(reader)

        return events

    def filter_events_by_date(self, events: List[Dict]) -> List[Dict]:
        """Filter events to include only future events and recent past events"""
        now = self.TIMEZONE.localize(datetime.now())
        cutoff_date = now - timedelta(days=self.CALENDAR_RETENTION_DAYS)

        filtered_events = []
        for event_data in events:
            date_str = event_data.get("date", "")
            time_str = event_data.get("time") or self.DEFAULT_TIME

            try:
                event_dt = self.parse_datetime(date_str, time_str)
                if event_dt >= cutoff_date:
                    filtered_events.append(event_data)
            except ValueError as e:
                print(f"Warning: Skipping '{event_data.get('title')}' with unparseable date '{date_str}': {e}")

        return filtered_events

    def parse_datetime(self, date_str: str, time_str: str) -> datetime:
        """Parse a YYYY-MM-DD date and HH:MM time into a localized datetime

        Raises ValueError if the date can't be parsed; callers skip the event
        rather than guessing a date.
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d")

        parsed_time = self.parse_time(time_str)
        if parsed_time:
            dt = dt.replace(hour=parsed_time[0], minute=parsed_time[1])

        return self.TIMEZONE.localize(dt)

    @staticmethod
    def parse_time(time_str: Optional[str]) -> Optional[Tuple[int, int]]:
        """Return (hour, minute) for a valid 'HH:MM' / 'HH:MMhs', else None"""
        match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(hs)?", (time_str or "").strip())
        if not match:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            return None
        return hour, minute

    def create_event(self, event_data: Dict, uid_key: str = None,
                     previous: Dict[str, Tuple[str, datetime, int]] = None) -> Event:
        """Create an iCalendar event from event data

        uid_key: identity used to derive the UID (defaults to event_key)
        previous: UID -> (content hash, DTSTAMP, SEQUENCE) from the last
            generated files, so unchanged events keep their DTSTAMP and
            edits bump DTSTAMP and SEQUENCE
        """
        event = Event()

        title = event_data.get("title", "Film Screening")
        has_time = self.parse_time(event_data.get("time")) is not None
        # No known time: all-day event flagged for the user, rather than a guessed hour
        event.add("summary", title if has_time else f"{title} {self.NO_TIME_NOTE}")

        description_parts = []

        rating = event_data.get("rating", "")
        duration = event_data.get("duration", "")
        if rating or duration:
            info_parts = []
            if rating:
                info_parts.append(f"IMDb: {rating}/10")
            if duration:
                info_parts.append(f"{duration} min")
            description_parts.append(" | ".join(info_parts))

        if event_data.get("description"):
            description_parts.append(event_data["description"])

        venue = event_data.get("venue", "")
        if venue:
            description_parts.append(f"\nVenue: {venue}")

        if event_data.get("url"):
            description_parts.append(f"\nMore info: {event_data['url']}")

        event.add("description", "\n".join(description_parts))

        if event_data.get("url"):
            event.add("url", event_data["url"])

        if venue:
            event.add("location", venue)

        date_str = event_data.get("date", "")
        start_dt = self.parse_datetime(date_str, event_data.get("time") or "")

        if not has_time:
            event.add("dtstart", start_dt.date())
            event.add("dtend", start_dt.date() + timedelta(days=1))
        else:
            event.add("dtstart", start_dt)
            event.add("dtend", start_dt + timedelta(minutes=self._duration_minutes(event_data)))

        uid_key = uid_key or event_key(event_data)
        uid = hashlib.sha1(uid_key.encode("utf-8")).hexdigest()[:20] + "@lumiton.ar"
        event.add("uid", uid)

        event.add("status", "CONFIRMED")

        # DTSTAMP = when this event last changed (RFC 5545), not generation
        # time, so unchanged events don't rewrite the file on every run.
        # The hash covers the source data (not icalendar's serialization), so
        # a library upgrade doesn't look like every event changed.
        content_hash = self.content_hash(event_data)
        prev = (previous or {}).get(uid)
        if prev is None:
            dtstamp, sequence = self.run_stamp, 0
        elif prev[0] == content_hash:
            dtstamp, sequence = prev[1], prev[2]
        else:
            dtstamp, sequence = self.run_stamp, prev[2] + 1
        event.add("dtstamp", dtstamp)
        event.add("sequence", sequence)
        event.add(self.HASH_PROP, content_hash)

        return event

    @staticmethod
    def _duration_minutes(event_data: Dict) -> int:
        """Runtime from IMDb (default 120) plus a 5-minute buffer"""
        duration_minutes = 120
        duration_str = event_data.get("duration", "")
        if duration_str:
            try:
                duration_minutes = int(duration_str)
            except (ValueError, TypeError):
                pass

        return duration_minutes + 5

    @classmethod
    def content_hash(cls, event_data: Dict) -> str:
        """Hash of the source fields that end up in the ICS event"""
        fields = [(event_data.get(f) or "") for f in cls.HASHED_FIELDS]
        return hashlib.sha1(json.dumps(fields).encode("utf-8")).hexdigest()

    def load_previous(self, filepaths: List[Path]) -> Dict[str, Tuple[str, datetime, int]]:
        """Read UID -> (content hash, DTSTAMP, SEQUENCE) from previously generated files

        All files share one map so an event has the same DTSTAMP/SEQUENCE in
        the combined calendar and in its venue calendar.
        """
        previous = {}
        for filepath in filepaths:
            if not filepath.exists():
                continue
            try:
                cal = Calendar.from_ical(filepath.read_bytes())
            except Exception as e:
                print(f"Warning: Could not read previous calendar {filepath}: {e}")
                continue
            for component in cal.walk("VEVENT"):
                content_hash = component.get(self.HASH_PROP)
                dtstamp = component.get("dtstamp")
                if not (content_hash and dtstamp):
                    continue
                entry = (str(content_hash), dtstamp.dt, int(component.get("sequence", 0)))
                uid = str(component.get("uid"))
                # On disagreement between files, trust the most recent revision
                if uid not in previous or entry[2] > previous[uid][2]:
                    previous[uid] = entry
        return previous

    def generate_calendar(self, events: List[Dict], calendar_name: str,
                          previous: Dict[str, Tuple[str, datetime, int]] = None) -> Calendar:
        """Generate a calendar from list of events"""
        cal = Calendar()

        cal.add("prodid", "-//Lumiton Agenda//lumiton.ar//")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", calendar_name)
        cal.add("x-wr-timezone", "America/Argentina/Buenos_Aires")
        cal.add("x-wr-caldesc", f"Film screenings from Lumiton - {calendar_name}")

        for uid_key, event_data in keyed_events(events):
            try:
                event = self.create_event(event_data, uid_key, previous)
                cal.add_component(event)
            except Exception as e:
                print(f"Warning: Failed to create event for {event_data.get('title')}: {e}")

        return cal

    def save_calendar(self, calendar: Calendar, filepath: Path):
        """Save calendar to ICS file with LF line endings"""
        ical_data = calendar.to_ical()
        ical_data = ical_data.replace(b'\r\n', b'\n')
        with open(filepath, "wb") as f:
            f.write(ical_data)
        print(f"Saved calendar to {filepath}")

    def generate_all(self):
        """Generate all calendar files"""
        previous = self.load_previous(sorted(self.output_dir.glob("*.ics")))

        all_events_csv = self.data_dir / "all_events.csv"
        if all_events_csv.exists():
            all_events = self.read_csv(all_events_csv)
            if all_events:
                filtered_events = self.filter_events_by_date(all_events)
                ics_file = self.output_dir / "all_events.ics"
                cal = self.generate_calendar(filtered_events, "Lumiton - All Events", previous)
                self.save_calendar(cal, ics_file)
                print(f"Generated combined calendar with {len(filtered_events)} events (filtered from {len(all_events)} total)")

        for venue_name in VENUES:
            venue_file = venue_slug(venue_name)
            csv_file = self.data_dir / f"{venue_file}.csv"
            if csv_file.exists():
                # Generate even when empty, so a venue with no events
                # publishes an empty calendar rather than a stale one
                all_events = self.read_csv(csv_file)
                filtered_events = self.filter_events_by_date(all_events)
                ics_file = self.output_dir / f"{venue_file}.ics"
                cal = self.generate_calendar(filtered_events, f"Lumiton - {venue_name}", previous)
                self.save_calendar(cal, ics_file)
                print(f"Generated {venue_name} calendar with {len(filtered_events)} events (filtered from {len(all_events)} total)")


def main():
    """Main entry point"""
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    calendars_dir = base_dir / "calendars"

    generator = CalendarGenerator(data_dir, calendars_dir)
    generator.generate_all()

    print("\nCalendar generation completed!")


if __name__ == "__main__":
    main()
