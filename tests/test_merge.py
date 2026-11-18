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


def showings(rows):
    return sorted((r["title"], r["date"], r["venue"], r["time"]) for r in rows)


def test_showing_moved_to_another_venue_or_date_is_dropped(scraper):
    old = [row("ALIEN", day=2, venue="Centro Cultural Munro"), row("CIENAGA", day=4)]
    fresh = [row("ALIEN", day=4), row("CIENAGA", day=2)]
    assert showings(merge(scraper, old, fresh)) == showings(fresh)


def test_unlisted_showing_without_a_new_one_is_kept(scraper):
    # Listed at two venues; the Munro one failed to parse: no new showing
    old = [row("X", day=2, venue="Centro Cultural Munro"), row("X", day=4)]
    assert showings(merge(scraper, old, [row("X", day=4)])) == showings(old)


def test_moves_pair_one_to_one_nearest_date_first(scraper):
    # Two unlisted showings, one new: only the nearest one moved
    old = [row("X", day=2), row("X", day=9), row("X", day=12)]
    fresh = [row("X", day=3), row("X", day=12)]
    merged = {r["date"] for r in merge(scraper, old, fresh)}
    assert merged == {row("X", day=d)["date"] for d in (3, 9, 12)}


def test_no_moves_when_the_scrape_skipped_events(scraper):
    scraper.parse_failures = 1
    old = [row("ALIEN", day=2, venue="Centro Cultural Munro")]
    fresh = [row("ALIEN", day=4)]
    assert len(merge(scraper, old, fresh)) == 2


def test_moved_showing_that_already_happened_is_kept(scraper):
    old = [row("ALIEN", day=-1)]
    assert len(merge(scraper, old, [row("ALIEN", day=3)])) == 2


def test_row_with_unreadable_date_is_not_treated_as_moved(scraper):
    old = [row("ALIEN", time="18hs", day=2)]
    old[0]["date"] = "sometime"
    assert len(merge(scraper, old, [row("ALIEN", day=3)])) == 2


def test_moved_showing_keeps_its_time_when_the_new_one_has_none(scraper):
    old = [row("ALIEN", day=2, venue="Centro Cultural Munro", time="18:30")]
    fresh = [row("ALIEN", day=4)]
    del fresh[0]["time"]
    merged = merge(scraper, old, fresh)
    assert showings(merged) == [("ALIEN", row(day=4)["date"], "Cine York", "18:30")]


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
