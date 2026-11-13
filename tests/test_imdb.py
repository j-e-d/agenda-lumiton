import csv
import io

import pytest

import imdb_dataset
from imdb_dataset import IMDbDataset

# (tconst, type, primary title, original title, year, runtime, rating, votes)
TITLES = [
    ("tt1", "movie", "2001: A Space Odyssey", "2001: A Space Odyssey", 1968, 149, 8.3, 796549),
    ("tt2", "movie", "Odisea en el espacio", "Odisea en el espacio", 2004, 118, 7.7, 1057),
    ("tt3", "movie", "Ben-Hur", "Ben-Hur", 1959, 212, 8.1, 260000),
    ("tt4", "movie", "Ben-Hur", "Ben-Hur", 2016, 123, 5.7, 140000),
    ("tt5", "short", "Hur", "Hur", 2016, 12, 6.9, 30),
    ("tt6", "movie", "The Shining", "The Shining", 1980, 146, 8.4, 1252512),
    ("tt7", "movie", "Psycho", "Psycho", 1960, 109, 8.5, 750000),
    ("tt8", "movie", "Psycho", "Psycho", 1998, 105, 4.6, 45000),
    ("tt9", "movie", "Animal", "Animal", 2023, 201, 6.1, 90000),
    ("tt10", "movie", "Animal", "Animal", 2014, 86, 4.7, 30000),
    ("tt11", "short", "La pesca", "La pesca", 2015, 14, 7.0, 40),
    ("tt12", "movie", "La pesca", "La pesca", 1999, 95, 6.0, 4000),
    (
        "tt13",
        "movie",
        "Kill Bill: The Whole Bloody Affair",
        "Kill Bill: The Whole Bloody Affair",
        2004,
        253,
        8.7,
        68091,
    ),
    ("tt14", "movie", "Too Few Votes", "Too Few Votes", 2020, 90, 9.9, 5),
]
AKAS = [("tt1", "2001: Odisea del espacio", "AR"), ("tt6", "El resplandor", "AR"), ("tt6", "Le shining", "FR")]


def tsv(header, rows):
    lines = ["\t".join(header)] + ["\t".join(map(str, r)) for r in rows]
    return csv.DictReader(io.StringIO("\n".join(lines) + "\n"), delimiter="\t", quoting=csv.QUOTE_NONE)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    files = {
        "title.ratings": lambda: tsv(["tconst", "averageRating", "numVotes"], [(t[0], t[6], t[7]) for t in TITLES]),
        "title.basics": lambda: tsv(
            [
                "tconst",
                "titleType",
                "primaryTitle",
                "originalTitle",
                "isAdult",
                "startYear",
                "endYear",
                "runtimeMinutes",
                "genres",
            ],
            [(t[0], t[1], t[2], t[3], 0, t[4], "\\N", t[5], "Drama") for t in TITLES],
        ),
        "title.akas": lambda: tsv(
            ["titleId", "ordering", "title", "region", "language", "types", "attributes", "isOriginalTitle"],
            [(a[0], 1, a[1], a[2], "\\N", "\\N", "\\N", 0) for a in AKAS],
        ),
    }
    path = tmp_path_factory.mktemp("imdb") / "imdb.sqlite"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(imdb_dataset, "_stream_tsv", lambda name: files[name]())
        imdb_dataset.build(path)
    return IMDbDataset(path)


def year_of(dataset, title, is_short=False):
    match = dataset.lookup(title, is_short)
    return match and match[0]


@pytest.mark.parametrize(
    "title, year",
    [
        ("EL RESPLANDOR", 1980),  # Spanish aka
        ("EL RESPLANDOR (THE SHINING)", 1980),  # full, then parts in parens
        ("KILL BILL: THE WHOLE BLOODY AFFAIR", 2004),
        ("PSYCHO", 1960),  # dominant by votes
        ("PSYCHO (1998)", 1998),  # year hint
        ("PSYCHO – 1999", 1998),  # within ±1 year
    ],
)
def test_matches(dataset, title, year):
    assert year_of(dataset, title) == year


@pytest.mark.parametrize(
    "title",
    [
        "PSYCHO (1985)",  # year hint too far from any Psycho
        "ANIMAL",  # no title dominates: ambiguous
        "BEN - HUR",  # ambiguous; must not fall back to 'hur'
        "2001: ODISEA EN EL ESPACIO",  # number prefix: not 'odisea en el espacio'
        "TOO FEW VOTES",  # below MIN_VOTES, not indexed
        "LE SHINING",  # aka from a region we don't index
    ],
)
def test_no_match(dataset, title):
    assert dataset.lookup(title) is None


def test_short_film_description_restricts_to_shorts(dataset):
    assert year_of(dataset, "LA PESCA") == 1999
    assert year_of(dataset, "LA PESCA", is_short=True) == 2015
    info = dataset.get_movie_info("LA PESCA", "Cortometraje de 14 minutos")
    assert info == {"rating": "7.0", "duration": "14", "imdb_id": "tt11"}


def test_get_movie_info_formats_csv_strings(dataset):
    assert dataset.get_movie_info("2001: A SPACE ODYSSEY") == {"rating": "8.3", "duration": "149", "imdb_id": "tt1"}
    assert dataset.get_movie_info("ANIMAL") == {"rating": "", "duration": "", "imdb_id": ""}


def test_number_titles_are_not_year_hints():
    names, year = IMDbDataset.candidates("1977")
    assert (names, year) == (["1977"], None)
    assert IMDbDataset.candidates("BLADE RUNNER 2049")[1] is None


def test_missing_index_skips_lookups(tmp_path):
    assert IMDbDataset(tmp_path / "none.sqlite").get_movie_info("PSYCHO") == {
        "rating": "",
        "duration": "",
        "imdb_id": "",
    }
