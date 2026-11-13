#!/usr/bin/env python3
"""
Calendar Generator
Converts CSV event data to ICS calendar files
"""

import contextlib
import csv
import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytz
from icalendar import Calendar, Event, Timezone, TimezoneStandard

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
    # Fields added later: hashed only when set, so adding a field doesn't
    # make every event without it look changed (and bump its SEQUENCE)
    OPTIONAL_HASHED_FIELDS = ("imdb_id",)

    def __init__(self, data_dir: Path, output_dir: Path, docs_dir: Path | None = None):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        # Where the GitHub Pages site lives; gets upcoming.json when set
        self.docs_dir = Path(docs_dir) if docs_dir else None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_stamp = datetime.now(UTC).replace(microsecond=0)

    def read_csv(self, filepath: Path) -> list[dict]:
        """Read events from CSV file"""
        events = []

        if not filepath.exists():
            print(f"Warning: {filepath} does not exist")
            return events

        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            events = list(reader)

        return events

    def filter_events_by_date(self, keyed: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
        """Keep (key, event) pairs for future events and recent past events"""
        cutoff_date = datetime.now(self.TIMEZONE) - timedelta(days=self.CALENDAR_RETENTION_DAYS)

        filtered = []
        for key, event_data in keyed:
            date_str = event_data.get("date", "")
            time_str = event_data.get("time") or self.DEFAULT_TIME

            try:
                if self.parse_datetime(date_str, time_str) >= cutoff_date:
                    filtered.append((key, event_data))
            except ValueError as e:
                print(f"Warning: Skipping '{event_data.get('title')}' with unparseable date '{date_str}': {e}")

        return filtered

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
    def parse_time(time_str: str | None) -> tuple[int, int] | None:
        """Return (hour, minute) for a valid 'HH:MM' / 'HH:MMhs', else None"""
        match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(hs)?", (time_str or "").strip())
        if not match:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            return None
        return hour, minute

    def create_event(
        self, event_data: dict, uid_key: str | None = None, previous: dict[str, tuple[str, datetime, int]] | None = None
    ) -> Event:
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
        if event_data.get("imdb_id"):
            # Link to the matched title, so a wrong match is easy to spot
            description_parts.append(f"https://www.imdb.com/title/{event_data['imdb_id']}/")

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
    def vtimezone() -> Timezone:
        """VTIMEZONE for the TZID used by DTSTART/DTEND (RFC 5545 §3.6.5)

        Argentina has stayed on UTC-3 without DST since 2009, so a single
        STANDARD rule describes every date this calendar contains.
        """
        tz = Timezone()
        tz.add("tzid", "America/Argentina/Buenos_Aires")
        standard = TimezoneStandard()
        standard.add("dtstart", datetime(1970, 1, 1))
        standard.add("tzoffsetfrom", timedelta(hours=-3))
        standard.add("tzoffsetto", timedelta(hours=-3))
        standard.add("tzname", "-03")
        tz.add_component(standard)
        return tz

    @staticmethod
    def _duration_minutes(event_data: dict) -> int:
        """Runtime from IMDb (default 120) plus a 5-minute buffer"""
        duration_minutes = 120
        duration_str = event_data.get("duration", "")
        if duration_str:
            with contextlib.suppress(ValueError, TypeError):
                duration_minutes = int(duration_str)

        return duration_minutes + 5

    @classmethod
    def content_hash(cls, event_data: dict) -> str:
        """Hash of the source fields that end up in the ICS event"""
        fields = [(event_data.get(f) or "") for f in cls.HASHED_FIELDS]
        fields += [f"{f}={event_data[f]}" for f in cls.OPTIONAL_HASHED_FIELDS if event_data.get(f)]
        return hashlib.sha1(json.dumps(fields).encode("utf-8")).hexdigest()

    def load_previous(self, filepaths: list[Path]) -> dict[str, tuple[str, datetime, int]]:
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

    def generate_calendar(
        self,
        keyed: list[tuple[str, dict]],
        calendar_name: str,
        previous: dict[str, tuple[str, datetime, int]] | None = None,
    ) -> Calendar:
        """Generate a calendar from (UID key, event) pairs"""
        cal = Calendar()

        cal.add("prodid", "-//Lumiton Agenda//lumiton.ar//")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", calendar_name)
        cal.add("x-wr-timezone", "America/Argentina/Buenos_Aires")
        cal.add("x-wr-caldesc", f"Film screenings from Lumiton - {calendar_name}")
        cal.add_component(self.vtimezone())

        for uid_key, event_data in keyed:
            try:
                event = self.create_event(event_data, uid_key, previous)
                cal.add_component(event)
            except Exception as e:
                print(f"Warning: Failed to create event for {event_data.get('title')}: {e}")

        return cal

    def save_calendar(self, calendar: Calendar, filepath: Path):
        """Save calendar to ICS file with CRLF line endings (RFC 5545 §3.1)

        .gitattributes marks *.ics as -text so git stores and serves the
        CRLF bytes unchanged.
        """
        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
        tmp_path.write_bytes(calendar.to_ical())
        os.replace(tmp_path, filepath)
        print(f"Saved calendar to {filepath}")

    def generate_all(self):
        """Generate all calendar files

        Keys (and so UIDs) are computed once over the full combined dataset,
        before the date filter, so an event's UID doesn't depend on which
        other rows happen to be inside the window or in which calendar it is.
        Venue calendars are views of the combined data, like the venue CSVs.
        """
        all_events_csv = self.data_dir / "all_events.csv"
        if not all_events_csv.exists():
            # Don't overwrite published calendars with empty ones
            print(f"Warning: {all_events_csv} not found; calendars left unchanged")
            return

        # all_events.ics holds every event; venue files are only a fallback
        # for when it's missing or unreadable
        combined = self.output_dir / "all_events.ics"
        previous = self.load_previous([combined])
        if not previous:
            previous = self.load_previous(sorted(self.output_dir.glob("*.ics")))
        all_events = self.read_csv(all_events_csv)
        keyed = self.filter_events_by_date(keyed_events(all_events))

        calendars = [("all_events", "Lumiton - All Events", keyed, len(all_events))]
        for venue_name in VENUES:
            # Always generated, so a venue with no events publishes an empty
            # calendar rather than a stale one
            venue_keyed = [(k, e) for k, e in keyed if e.get("venue") == venue_name]
            venue_total = sum(1 for e in all_events if e.get("venue") == venue_name)
            calendars.append((venue_slug(venue_name), f"Lumiton - {venue_name}", venue_keyed, venue_total))

        for slug, name, events, total in calendars:
            cal = self.generate_calendar(events, name, previous)
            self.save_calendar(cal, self.output_dir / f"{slug}.ics")
            print(f"Generated {name} calendar with {len(events)} events (filtered from {total} total)")

        if self.docs_dir:
            self.save_screening_dates({slug: events for slug, _, events, _ in calendars})

    def save_screening_dates(self, calendars: dict[str, list[tuple[str, dict]]]):
        """Write docs/upcoming.json: each calendar's screening dates

        The page uses it to mark venues with no upcoming screenings. Dates,
        not counts: the page compares them with today, so the file only
        changes when the calendars do.
        """
        assert self.docs_dir is not None
        dates = {slug: sorted({e["date"] for _, e in events}) for slug, events in calendars.items()}
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        path = self.docs_dir / "upcoming.json"
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(dates, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)


def main():
    """Main entry point"""
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    calendars_dir = base_dir / "calendars"

    generator = CalendarGenerator(data_dir, calendars_dir, base_dir / "docs")
    generator.generate_all()

    print("\nCalendar generation completed!")


if __name__ == "__main__":
    main()
