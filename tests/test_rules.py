from scripts.rules import match_items


def _item(rk, title, **fields):
    return {"ratingKey": rk, "title": title, **fields}


def test_match_by_field_equality():
    items = [
        _item("1", "A", director="Nolan"),
        _item("2", "B", director="Scott"),
        _item("3", "C", director="Nolan"),
    ]
    matched = match_items(items, {"director": "Nolan"})
    assert [i["ratingKey"] for i in matched] == ["1", "3"]


def test_match_by_explicit_titles():
    items = [_item("1", "A"), _item("2", "B"), _item("3", "C")]
    matched = match_items(items, {"titles": ["A", "C"]})
    assert [i["ratingKey"] for i in matched] == ["1", "3"]


def test_empty_criteria_matches_nothing():
    items = [_item("1", "A")]
    assert match_items(items, {}) == []


def test_mixed_titles_and_field_use_or_semantics():
    items = [
        _item("1", "A", director="Scott"),   # title matches only
        _item("2", "B", director="Nolan"),   # field matches only
        _item("3", "C", director="Scott"),   # neither matches
    ]
    matched = match_items(items, {"titles": ["A"], "director": "Nolan"})
    assert [i["ratingKey"] for i in matched] == ["1", "2"]
