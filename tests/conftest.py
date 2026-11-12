import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

# The scraper modules import each other as top-level modules
sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))

from calendar_generator import CalendarGenerator  # noqa: E402
from imdb_dataset import IMDbDataset  # noqa: E402
from scraper import LumitonScraper  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class NoIMDb:
    """IMDb stub: records lookups, never matches"""

    def __init__(self):
        self.calls = []

    def get_movie_info(self, title, description=""):
        self.calls.append(title)
        return {"rating": "", "duration": ""}


class NoNetwork:
    """Session stand-in: any request fails loudly; tests stub the fetch"""

    def __init__(self):
        self.closed = False

    def get(self, *args, **kwargs):
        raise AssertionError("tests must not access the network; stub fetch_page")

    def close(self):
        self.closed = True


class OfflineScraper(LumitonScraper):
    """LumitonScraper without network access or IMDb index

    Records retry waits and sessions instead of sleeping/connecting.
    """

    def __init__(self):
        self.waits: list[float] = []
        self.sessions: list[NoNetwork] = [NoNetwork()]
        super().__init__(session=self.sessions[0], imdb=cast(IMDbDataset, NoIMDb()))

    def _wait(self, seconds: float):
        self.waits.append(seconds)

    def _new_session(self):
        self.sessions.append(NoNetwork())
        return self.sessions[-1]

    def _fetch_time_from_detail_page(self, url: str) -> str | None:
        return None


@pytest.fixture
def scraper():
    return OfflineScraper()


def days_from_today(n: int) -> str:
    # The code under test works in Buenos Aires time, not the machine's
    today = datetime.now(CalendarGenerator.TIMEZONE).date()
    return (today + timedelta(days=n)).isoformat()


def row(title="FILM", day=10, time="20:30", venue="Cine York", url=None, **extra):
    """An event row `day` days from today"""
    r = {
        "title": title,
        "date": days_from_today(day),
        "time": time,
        "venue": venue,
        "url": f"https://lumiton.ar/evento/{title.lower()}/" if url is None else url,
        "description": "",
        "rating": "",
        "duration": "",
    }
    r.update(extra)
    return r
