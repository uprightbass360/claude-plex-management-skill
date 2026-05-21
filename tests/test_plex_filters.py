import pytest
from scripts.rules import criteria_to_plex_filters


def test_single_genre():
    assert criteria_to_plex_filters({"genre": "Horror"}) == {"genre": "Horror"}


def test_single_actor():
    assert criteria_to_plex_filters({"actor": "Bruce Willis"}) == {"actor": "Bruce Willis"}


def test_decade_single():
    assert criteria_to_plex_filters({"decade": 1980}) == {"decade": 1980}


def test_year_range_two_clauses_anded():
    out = criteria_to_plex_filters({"year_from": 1980, "year_to": 1989})
    assert out == {"and": [{"year>>": 1980}, {"year<<": 1989}]}


def test_genre_and_decade_anded():
    out = criteria_to_plex_filters({"genre": "Horror", "decade": 1980})
    assert out == {"and": [{"genre": "Horror"}, {"decade": 1980}]}


def test_rating_list_becomes_or_tree():
    out = criteria_to_plex_filters({"rating": ["G", "PG"]})
    assert out == {"or": [{"contentRating": "G"}, {"contentRating": "PG"}]}


def test_rating_single_scalar():
    assert criteria_to_plex_filters({"rating": "R"}) == {"contentRating": "R"}


def test_empty_raises():
    with pytest.raises(ValueError):
        criteria_to_plex_filters({})
