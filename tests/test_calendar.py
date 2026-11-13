import csv
import json

import pytest
from icalendar import Calendar

from calendar_generator import CalendarGenerator
from conftest import row

FIELDS = ["title", "date", "time", "venue", "url", "description", "rating", "duration", "imdb_id"]


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


def test_imdb_link_in_description(dirs):
    out = generate(dirs, [row("A", rating="8.3", duration="149", imdb_id="tt0062622"), row("B")])
    found = events(out / "all_events.ics")
    assert "IMDb: 8.3/10 | 149 min\nhttps://www.imdb.com/title/tt0062622/" in str(found["A"]["description"])
    assert "imdb.com" not in str(found["B"]["description"])


def test_upcoming_json_lists_each_calendars_dates(dirs, tmp_path):
    data, out = dirs
    docs = tmp_path / "docs"
    docs.mkdir()
    rows = [row("A", day=3, venue="Cine York"), row("B", day=5, venue="Cine York"), row("OLD", day=-40)]
    write_csv(data / "all_events.csv", rows)
    CalendarGenerator(data, out, docs).generate_all()
    dates = json.loads((docs / "upcoming.json").read_text(encoding="utf-8"))
    assert dates["cine_york"] == [rows[0]["date"], rows[1]["date"]]
    assert dates["torre_ader"] == []
    assert set(dates) == {
        "all_events",
        "lumiton",
        "cine_york",
        "centro_cultural_munro",
        "quinta_trabucco",
        "torre_ader",
    }


def test_no_docs_dir_writes_no_json(dirs, tmp_path):
    generate(dirs, [row("A")])
    assert not list(tmp_path.rglob("upcoming.json"))


def test_events_without_imdb_id_keep_their_hash():
    event = row("A")
    without_field = {k: v for k, v in event.items() if k != "imdb_id"}
    assert CalendarGenerator.content_hash(event) == CalendarGenerator.content_hash(without_field)
    assert CalendarGenerator.content_hash(event | {"imdb_id": "tt1"}) != CalendarGenerator.content_hash(event)


def test_upcoming_json_creates_docs_dir(dirs, tmp_path):
    data, out = dirs
    write_csv(data / "all_events.csv", [row("A")])
    CalendarGenerator(data, out, tmp_path / "missing" / "docs").generate_all()
    assert (tmp_path / "missing" / "docs" / "upcoming.json").exists()
