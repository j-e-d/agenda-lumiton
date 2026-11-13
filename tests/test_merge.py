import csv

import pytest

from conftest import row


def times(rows):
    return sorted(r["time"] for r in rows)


def merge(scraper, old, fresh):
    return scraper._merge([dict(r) for r in old], [dict(r) for r in fresh])


def test_new_event_is_appended(scraper):
    merged = merge(scraper, [row("A")], [row("A"), row("B")])
    assert [r["title"] for r in merged] == ["A", "B"]


def test_groups_missing_from_scrape_are_kept(scraper):
    merged = merge(scraper, [row("A"), row("B")], [row("B")])
    assert [r["title"] for r in merged] == ["A", "B"]


def test_retimed_showing_replaces_old_time(scraper):
    merged = merge(scraper, [row(time="18:00")], [row(time="19:30")])
    assert times(merged) == ["19:30"]


def test_removed_upcoming_showing_is_dropped(scraper):
    old = [row(time="18:00"), row(time="21:00")]
    assert times(merge(scraper, old, [row(time="21:00")])) == ["21:00"]


def test_past_showing_is_kept_when_site_drops_it(scraper):
    # 18:00 already started today; the site now lists only 21:00
    scraper._has_started = lambda r, now: r["time"] == "18:00"
    old = [row(day=0, time="18:00"), row(day=0, time="21:00")]
    merged = merge(scraper, old, [row(day=0, time="21:00")])
    assert times(merged) == ["18:00", "21:00"]


def test_unknown_time_takes_the_single_leftover_old_time(scraper):
    old = [row(time="18:00"), row(time="21:00")]
    fresh = [row(time="21:00"), {k: v for k, v in row().items() if k != "time"}]
    assert times(merge(scraper, old, fresh)) == ["18:00", "21:00"]


def test_unknown_time_is_not_guessed_when_ambiguous(scraper):
    old = [row(time="18:00"), row(time="21:00")]
    fresh = [row(time="19:30"), {k: v for k, v in row().items() if k != "time"}]
    assert times(merge(scraper, old, fresh)) == ["", "19:30"]


def test_rating_carried_over_by_url_without_lookup(scraper):
    old = [row(day=-40, rating="8.1", duration="99", imdb_id="tt42")]
    merged = merge(scraper, old, [row(day=10)])
    assert (merged[-1]["rating"], merged[-1]["duration"], merged[-1]["imdb_id"]) == ("8.1", "99", "tt42")
    assert scraper.imdb.calls == []


def test_rating_does_not_bleed_between_urlless_events(scraper):
    old = [row("A", url="", rating="8.1", duration="99")]
    merged = merge(scraper, old, [row("B", url="")])
    assert merged[-1]["rating"] == ""


def test_unreadable_csv_fails_instead_of_wiping_history(scraper, tmp_path):
    (tmp_path / "all_events.csv").write_bytes(b"title,date\n\xff\xfe broken\n")
    before = (tmp_path / "all_events.csv").read_bytes()
    scraper.events = [row()]
    with pytest.raises(UnicodeDecodeError):
        scraper.save_to_csv(tmp_path)
    assert (tmp_path / "all_events.csv").read_bytes() == before


def test_save_writes_combined_and_venue_views(scraper, tmp_path):
    scraper.events = [row("A", venue="Cine York"), row("B", venue="Lumiton")]
    scraper.save_to_csv(tmp_path)
    with open(tmp_path / "cine_york.csv", encoding="utf-8") as f:
        york = list(csv.DictReader(f))
    assert [r["title"] for r in york] == ["A"]
    assert (tmp_path / "torre_ader.csv").exists()


def test_carry_over_prefers_row_with_imdb_id(scraper):
    old = [row(day=-40, rating="6.5"), row(day=-30, rating="6.5", imdb_id="tt123")]
    merged = merge(scraper, old, [row(day=10)])
    assert merged[-1]["imdb_id"] == "tt123"
