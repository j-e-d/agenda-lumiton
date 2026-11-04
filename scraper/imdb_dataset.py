#!/usr/bin/env python3
"""
IMDb dataset lookup

Builds a small SQLite index from IMDb's non-commercial datasets
(https://developer.imdb.com/non-commercial-datasets/) and looks up rating
and runtime for scraped titles. Replaces Cinemagoer, whose web scraping is
blocked by IMDb.

Build (streams ~760 MB, writes a few tens of MB):
    uv run scraper/imdb_dataset.py build [path]
"""

import csv
import gzip
import io
import re
import sqlite3
import sys
import unicodedata
import urllib.request
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

DATASET_URL = "https://datasets.imdbws.com/{name}.tsv.gz"
DEFAULT_DB = Path(__file__).parent.parent / ".cache" / "imdb.sqlite"

TITLE_TYPES = {"movie", "tvMovie", "short", "tvSpecial", "video"}
# Titles with fewer votes are almost never what a cinema is screening and
# would mostly add false matches
MIN_VOTES = 20
AKA_REGIONS = {"AR", "ES", "MX", "UY", "CL", "US", "GB", "XWW"}
# Without a year hint, only trust the most-voted match if it clearly
# dominates (e.g. Psycho 1960 vs the 1998 remake); otherwise the title is
# ambiguous (ANIMAL, SABRINA, DRÁCULA) and we'd rather report nothing
DOMINANCE_RATIO = 10
# Release year vs. year hint (festival/release dates often differ by one)
YEAR_TOLERANCE = 1
# Descriptions announcing a short film rule out feature-length matches
SHORT_FILM_RE = re.compile(r"\bcortometraje|\bcorto\b", re.IGNORECASE)
SHORT_FILM_MAX_MINUTES = 45

csv.field_size_limit(sys.maxsize)


def normalize(title: str) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces"""
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _stream_tsv(name: str) -> Iterator[Dict[str, str]]:
    url = DATASET_URL.format(name=name)
    print(f"[IMDb] Streaming {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "agenda-lumiton"})
    with urllib.request.urlopen(request, timeout=120) as response:
        with gzip.GzipFile(fileobj=response) as gz:
            text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
            yield from csv.DictReader(text, delimiter="\t", quoting=csv.QUOTE_NONE)


def _nullable_int(value: str) -> Optional[int]:
    return None if value == "\\N" else int(value)


def build(db_path: Path = DEFAULT_DB):
    """Download the datasets and write the slim lookup database"""
    ratings = {}
    for row in _stream_tsv("title.ratings"):
        votes = int(row["numVotes"])
        if votes >= MIN_VOTES:
            ratings[row["tconst"]] = (float(row["averageRating"]), votes)
    print(f"[IMDb] {len(ratings)} rated titles")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_suffix(".tmp")
    tmp_path.unlink(missing_ok=True)
    db = sqlite3.connect(tmp_path)
    db.executescript("""
        CREATE TABLE titles (tconst TEXT PRIMARY KEY, year INTEGER, runtime INTEGER,
                             rating REAL, votes INTEGER);
        CREATE TABLE names (name TEXT, tconst TEXT, UNIQUE(name, tconst));
    """)

    titles = {}
    for row in _stream_tsv("title.basics"):
        tconst = row["tconst"]
        if row["titleType"] not in TITLE_TYPES or tconst not in ratings:
            continue
        rating, votes = ratings[tconst]
        titles[tconst] = (_nullable_int(row["startYear"]), _nullable_int(row["runtimeMinutes"]), rating, votes)
        for title in (row["primaryTitle"], row["originalTitle"]):
            db.execute("INSERT OR IGNORE INTO names VALUES (?, ?)", (normalize(title), tconst))
    db.executemany("INSERT INTO titles VALUES (?, ?, ?, ?, ?)", ((k, *v) for k, v in titles.items()))
    print(f"[IMDb] {len(titles)} titles kept")

    for row in _stream_tsv("title.akas"):
        if row["titleId"] in titles and (row["region"] in AKA_REGIONS or row["isOriginalTitle"] == "1"):
            db.execute("INSERT OR IGNORE INTO names VALUES (?, ?)", (normalize(row["title"]), row["titleId"]))

    db.execute("CREATE INDEX names_name ON names(name)")
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp_path.replace(db_path)
    print(f"[IMDb] Wrote {db_path} ({db_path.stat().st_size // 1_000_000} MB)")


class IMDbDataset:
    """Looks up rating and runtime for scraped titles in the local index"""

    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db = None
        self.cache: Dict[Tuple[str, bool], Dict[str, str]] = {}
        if Path(db_path).exists():
            self.db = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
        else:
            print(f"Warning: IMDb index {db_path} not found; skipping IMDb lookups "
                  f"(build it with: uv run scraper/imdb_dataset.py build)")

    @staticmethod
    def candidates(title: str) -> Tuple[List[str], Optional[int]]:
        """Search names and an optional year hint from a scraped title

        'EL RESPLANDOR (THE SHINING)' -> el resplandor the shining,
            el resplandor, the shining
        'EL INFIERNO ESTÁ ENCANTADOR – GULP. 1985' / 'GULP (1985)' -> year 1985
        'KILL BILL: THE WHOLE BLOODY AFFAIR' -> full title, then the part
            after the colon (never the prefix: 'MADRES: HAXAN...' is not 'Madres')
        Titles that are or end in a number ('1977', 'BLADE RUNNER 2049')
        are left alone: a year only counts after punctuation or in parens.
        """
        year = None
        year_match = (re.search(r"\((19\d{2}|20\d{2})\)\s*$", title)
                      or re.search(r"[.,–-]\s*(19\d{2}|20\d{2})\s*$", title))
        if year_match and title[:year_match.start()].strip():
            year = int(year_match.group(1))
            title = title[:year_match.start()]

        names = [title]
        paren = re.search(r"\(([^)]+)\)", title)
        if paren:
            names += [title[:paren.start()], paren.group(1)]
        for sep in (" – ", " - ", ": "):
            if sep in title:
                names.append(title.split(sep)[-1])

        seen = []
        for name in map(normalize, names):
            if name and name not in seen:
                seen.append(name)
        return seen, year

    def lookup(self, title: str, is_short: bool = False) -> Optional[tuple]:
        """Best (year, runtime, rating, votes) match, or None if not confident

        With a year hint, the closest year wins. Without one, the most-voted
        title wins only if it has DOMINANCE_RATIO x the runner-up's votes.
        """
        names, year = self.candidates(title)
        for name in names:
            rows = self.db.execute(
                "SELECT t.year, t.runtime, t.rating, t.votes FROM names n "
                "JOIN titles t USING (tconst) WHERE n.name = ?", (name,)).fetchall()
            if is_short:
                rows = [r for r in rows if r[1] and r[1] <= SHORT_FILM_MAX_MINUTES]
            if not rows:
                continue
            if year:
                # A year hint only accepts titles from about that year
                near = [r for r in rows if r[0] and abs(r[0] - year) <= YEAR_TOLERANCE]
                return max(near, key=lambda r: r[3]) if near else None
            rows.sort(key=lambda r: -r[3])
            if len(rows) == 1 or rows[0][3] >= DOMINANCE_RATIO * rows[1][3]:
                return rows[0]
            return None
        return None

    def get_movie_info(self, title: str, description: str = "") -> Dict[str, str]:
        """Rating and duration as CSV strings ('' when unknown)"""
        is_short = bool(SHORT_FILM_RE.search(description or ""))
        cache_key = (title, is_short)
        if cache_key in self.cache:
            return self.cache[cache_key]

        info = {"rating": "", "duration": ""}
        if self.db is not None:
            match = self.lookup(title, is_short)
            if match:
                year, runtime, rating, _votes = match
                info = {"rating": f"{rating:.1f}" if rating else "",
                        "duration": str(runtime) if runtime else ""}
                print(f"[IMDb] '{title}' -> {year}, rating {info['rating']}, {info['duration']} min")
            else:
                print(f"[IMDb] No match for '{title}'")
        self.cache[cache_key] = info
        return info


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        build(Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB)
    else:
        print(__doc__)
