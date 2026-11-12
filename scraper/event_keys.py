"""
Identity of a screening, shared by the scraper (CSV dedupe) and the
calendar generator (ICS UIDs) so the two can't drift apart.
"""

from collections.abc import Iterable


def event_key(event: dict) -> str:
    """Base identity: URL, date and venue

    URL is the primary identifier as it's stable even when titles change.
    Date/venue handle the same film shown on several days or at several
    venues. Time is deliberately excluded: it gets filled in or rescheduled,
    and that must update the existing screening, not create a new one.
    """
    # Events without a link fall back to the title, so different films
    # without URLs on the same day/venue aren't treated as one screening
    identity = event.get("url") or event.get("title") or ""
    return "|".join((identity, event.get("date") or "", event.get("venue") or ""))


def keyed_events(events: Iterable[dict]) -> list[tuple[str, dict]]:
    """Pair each event with a unique key

    The earliest showing with a given base key keeps the plain key; any
    further same-day showings of that URL/venue get the time appended.
    Ordering by time (not by row order, which the merge and the site can
    reshuffle) keeps each showing's key stable: past showings stay in the
    data, so the earliest one doesn't change when a later one is added or
    an earlier one ends.
    """
    events = list(events)
    order = sorted(range(len(events)), key=lambda i: (event_key(events[i]), events[i].get("time") or "", i))
    seen = set()
    keys: list[str] = [""] * len(events)
    for i in order:
        event = events[i]
        base = event_key(event)
        key = base
        if key in seen:
            key = f"{base}|{event.get('time') or ''}"
        n = 2
        while key in seen:  # identical rows: keep keys unique anyway
            key = f"{base}|{event.get('time') or ''}|{n}"
            n += 1
        seen.add(key)
        keys[i] = key
    return list(zip(keys, events, strict=True))
