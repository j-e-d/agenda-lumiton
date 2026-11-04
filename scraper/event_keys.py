"""
Identity of a screening, shared by the scraper (CSV dedupe) and the
calendar generator (ICS UIDs) so the two can't drift apart.
"""

from typing import Dict, Iterable, List, Tuple


def event_key(event: Dict) -> str:
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


def keyed_events(events: Iterable[Dict]) -> List[Tuple[str, Dict]]:
    """Pair each event with a unique key

    The first event with a given base key keeps the plain key; any further
    same-day showings of that URL/venue get the time appended. Keeping the
    first one plain means an existing screening's key (and UID) doesn't
    change when a second showing is added later.
    """
    seen = set()
    result = []
    for event in events:
        base = event_key(event)
        key = base
        if key in seen:
            key = f"{base}|{event.get('time') or ''}"
        n = 2
        while key in seen:  # identical rows: keep keys unique anyway
            key = f"{base}|{event.get('time') or ''}|{n}"
            n += 1
        seen.add(key)
        result.append((key, event))
    return result
