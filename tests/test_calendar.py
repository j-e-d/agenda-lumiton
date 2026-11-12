import csv

import pytest
from icalendar import Calendar

from calendar_generator import CalendarGenerator
from conftest import row

FIELDS = ["title", "date", "time", "venue", "url", "description", "rating", "duration"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def dirs(tmp_path):
    data, out = tmp_path / "data", tmp_path / "calendars"
    data.mkdir()
    return data, out


def generate(dirs, rows):
    data, out = dirs
    write_csv(data / "all_events.csv", rows)
    CalendarGenerator(data, out).generate_all()
    return out


def events(path):
    cal = Calendar.from_ical(path.read_bytes())
    return {str(e["summary"]): e for e in cal.walk("VEVENT")}


def test_rerun_is_byte_identical(dirs):
    rows = [row("A", rating="7.5", duration="100"), row("B", time="", venue="Lumiton")]
    out = generate(dirs, rows)
    first = {p.name: p.read_bytes() for p in out.glob("*.ics")}
    generate(dirs, rows)
    assert {p.name: p.read_bytes() for p in out.glob("*.ics")} == first


def test_rfc5545_line_endings_and_timezone(dirs):
    out = generate(dirs, [row("A")])
    body = (out / "all_events.ics").read_bytes()
    assert b"\r\n" in body and b"\n" not in body.replace(b"\r\n", b"")
    assert b"BEGIN:VTIMEZONE" in body
    assert b"TZID:America/Argentina/Buenos_Aires" in body


def test_untimed_event_is_all_day_and_flagged(dirs):
    out = generate(dirs, [row("A", time="")])
    event = events(out / "all_events.ics")["A (confirmar horario)"]
    start, end = event["dtstart"].dt, event["dtend"].dt
    assert not hasattr(start, "hour")
    assert (end - start).days == 1


def test_end_uses_runtime_plus_buffer(dirs):
    out = generate(dirs, [row("A", time="20:00", duration="100")])
    event = events(out / "all_events.ics")["A"]
    assert (event["dtend"].dt - event["dtstart"].dt).seconds == 105 * 60


def test_change_bumps_sequence_and_keeps_uid(dirs):
    out = generate(dirs, [row("A", rating="7.7")])
    before = events(out / "all_events.ics")["A"]
    generate(dirs, [row("A", rating="8.3")])
    after = events(out / "all_events.ics")["A"]
    assert after["uid"] == before["uid"]
    assert int(after["sequence"]) == int(before["sequence"]) + 1


def test_uid_survives_sibling_leaving_window(dirs):
    early, late = row("A", day=-31, time="18:00"), row("A", day=-31, time="21:00")
    early["date"] = late["date"] = row(day=-31)["date"]
    current = row("A", day=5)
    out = generate(dirs, [early, late, current])
    uid = events(out / "all_events.ics")["A"]["uid"]
    generate(dirs, [late, current])
    assert events(out / "all_events.ics")["A"]["uid"] == uid


def test_old_events_drop_out_of_window(dirs):
    out = generate(dirs, [row("OLD", day=-40), row("NEW", day=3)])
    assert set(events(out / "all_events.ics")) == {"NEW"}


def test_venue_calendars_are_views(dirs):
    out = generate(dirs, [row("A", venue="Cine York"), row("B", venue="Lumiton")])
    assert set(events(out / "cine_york.ics")) == {"A"}
    assert set(events(out / "lumiton.ics")) == {"B"}
    assert events(out / "torre_ader.ics") == {}


def test_bad_row_is_skipped_not_fatal(dirs):
    out = generate(dirs, [row("A"), row("BROKEN") | {"date": "not-a-date"}])
    assert set(events(out / "all_events.ics")) == {"A"}


def test_missing_csv_leaves_calendars_untouched(dirs):
    data, out = dirs
    out.mkdir()
    (out / "all_events.ics").write_bytes(b"keep")
    CalendarGenerator(data, out).generate_all()
    assert (out / "all_events.ics").read_bytes() == b"keep"
