#!/usr/bin/env python3
"""
Calendar Generator
Converts CSV event data to ICS calendar files
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

from icalendar import Calendar, Event
import pytz


class CalendarGenerator:
    """Generates ICS calendar files from CSV event data"""

    TIMEZONE = pytz.timezone("America/Argentina/Buenos_Aires")
    VENUES = ["lumiton", "cine_york", "centro_cultural_munro"]
    CURRENT_YEAR = datetime.now().year

    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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

    def parse_datetime(self, date_str: str, time_str: str) -> datetime:
        """Parse date and time strings into datetime object"""

        try:
            if date_str.count("/") == 1:
                day, month = map(int, date_str.split("/"))
                year = self.CURRENT_YEAR

                current_month = datetime.now().month
                if month < current_month or (
                    month == current_month and day < datetime.now().day
                ):
                    year += 1

                date_str = f"{day}/{month}/{year}"

            dt = datetime.strptime(date_str, "%d/%m/%Y")

            if time_str:
                time_str = time_str.strip().replace("hs", "")
                time_parts = time_str.split(":")
                if len(time_parts) == 2:
                    hour, minute = map(int, time_parts)
                    dt = dt.replace(hour=hour, minute=minute)

            dt = self.TIMEZONE.localize(dt)
            return dt

        except Exception as e:
            print(f"Warning: Failed to parse date '{date_str}' time '{time_str}': {e}")
            return self.TIMEZONE.localize(datetime.now())

    def create_event(self, event_data: Dict) -> Event:
        """Create an iCalendar event from event data"""
        event = Event()

        title = event_data.get("title", "Film Screening")
        event.add("summary", title)

        description_parts = []
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
        time_str = event_data.get("time", "20:00")

        start_dt = self.parse_datetime(date_str, time_str)
        event.add("dtstart", start_dt)

        end_dt = start_dt + timedelta(hours=2)
        event.add("dtend", end_dt)

        uid = f"{start_dt.strftime('%Y%m%d%H%M')}-{venue.replace(' ', '-')}-{title[:20].replace(' ', '-')}@lumiton.ar"
        event.add("uid", uid)

        event.add("dtstamp", start_dt.astimezone(pytz.UTC))

        event.add("status", "CONFIRMED")

        return event

    def generate_calendar(self, events: List[Dict], calendar_name: str) -> Calendar:
        """Generate a calendar from list of events"""
        cal = Calendar()

        cal.add("prodid", "-//Lumiton Agenda//lumiton.ar//")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", calendar_name)
        cal.add("x-wr-timezone", "America/Argentina/Buenos_Aires")
        cal.add("x-wr-caldesc", f"Film screenings from Lumiton - {calendar_name}")

        for event_data in events:
            try:
                event = self.create_event(event_data)
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
        all_events_csv = self.data_dir / "all_events.csv"
        if all_events_csv.exists():
            events = self.read_csv(all_events_csv)
            if events:
                cal = self.generate_calendar(events, "Lumiton - All Events")
                self.save_calendar(cal, self.output_dir / "all_events.ics")
                print(f"Generated combined calendar with {len(events)} events")

        for venue_file in self.VENUES:
            csv_file = self.data_dir / f"{venue_file}.csv"
            if csv_file.exists():
                events = self.read_csv(csv_file)
                if events:
                    venue_name = venue_file.replace("_", " ").title()
                    cal = self.generate_calendar(events, f"Lumiton - {venue_name}")
                    self.save_calendar(cal, self.output_dir / f"{venue_file}.ics")
                    print(f"Generated {venue_name} calendar with {len(events)} events")


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
