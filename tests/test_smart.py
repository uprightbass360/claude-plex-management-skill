from scripts.rules import match_smart


def _item(rk, title, year=None, genres=None, directors=None, actors=None,
          rating=None):
    return {"ratingKey": rk, "title": title, "year": year,
            "genres": genres or [], "directors": directors or [],
            "actors": actors or [], "rating": rating}


def test_genre_contains_case_insensitive():
    items = [_item("1", "A", genres=["Horror", "Comedy"]),
             _item("2", "B", genres=["Drama"])]
    out = match_smart(items, {"genre": "horror"})
    assert [i["ratingKey"] for i in out] == ["1"]


def test_decade_range():
    items = [_item("1", "A", year=1984), _item("2", "B", year=1990),
             _item("3", "C", year=1989)]
    out = match_smart(items, {"decade": 1980})
    assert sorted(i["ratingKey"] for i in out) == ["1", "3"]


def test_year_from_to():
    items = [_item("1", "A", year=1975), _item("2", "B", year=1985),
             _item("3", "C", year=1995)]
    out = match_smart(items, {"year_from": 1980, "year_to": 1990})
    assert [i["ratingKey"] for i in out] == ["2"]


def test_rating_set():
    items = [_item("1", "A", rating="G"), _item("2", "B", rating="PG"),
             _item("3", "C", rating="R")]
    out = match_smart(items, {"rating": ["G", "PG"]})
    assert sorted(i["ratingKey"] for i in out) == ["1", "2"]


def test_and_semantics_across_criteria():
    items = [
        _item("1", "80s Horror", year=1984, genres=["Horror"]),
        _item("2", "90s Horror", year=1994, genres=["Horror"]),
        _item("3", "80s Comedy", year=1985, genres=["Comedy"]),
    ]
    out = match_smart(items, {"genre": "Horror", "decade": 1980})
    assert [i["ratingKey"] for i in out] == ["1"]  # must match BOTH


def test_director_contains():
    items = [_item("1", "A", directors=["John Carpenter"]),
             _item("2", "B", directors=["Other"])]
    out = match_smart(items, {"director": "John Carpenter"})
    assert [i["ratingKey"] for i in out] == ["1"]


def test_actor_contains_case_insensitive():
    items = [_item("1", "A", actors=["Bruce Campbell", "Ted Raimi"]),
             _item("2", "B", actors=["Someone Else"])]
    out = match_smart(items, {"actor": "bruce campbell"})
    assert [i["ratingKey"] for i in out] == ["1"]


def test_empty_criteria_matches_nothing():
    items = [_item("1", "A", year=1984)]
    assert match_smart(items, {}) == []
