from conftest import row
from event_keys import event_key, keyed_events


def test_key_ignores_time():
    assert event_key(row(time="18:00")) == event_key(row(time="21:00"))


def test_urlless_events_fall_back_to_title():
    a, b = row("A", url=""), row("B", url="")
    assert event_key(a) != event_key(b)


def test_earliest_showing_gets_plain_key_regardless_of_order():
    early, late = row(time="18:00"), row(time="21:00")
    forward = {e["time"]: k for k, e in keyed_events([early, late])}
    backward = {e["time"]: k for k, e in keyed_events([late, early])}
    assert forward == backward
    assert forward["18:00"] == event_key(early)
    assert forward["21:00"] == event_key(late) + "|21:00"


def test_keys_returned_in_input_order():
    events = [row(time="21:00"), row("OTHER"), row(time="18:00")]
    assert [e for _, e in keyed_events(events)] == events


def test_identical_rows_still_get_unique_keys():
    keys = [k for k, _ in keyed_events([row(), row(), row()])]
    assert len(set(keys)) == 3
