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
    return "|".join((event.get(f) or "") for f in ("url", "date", "venue"))


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
        key = event_key(event)
        if key in seen:
            key = f"{key}|{event.get('time') or ''}"
        seen.add(key)
        result.append((key, event))
    return result
