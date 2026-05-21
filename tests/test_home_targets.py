from scripts.rules import resolve_targets


def test_both_is_default():
    assert resolve_targets("both") == ("home", "recommended")


def test_home_only():
    assert resolve_targets("home") == ("home",)


def test_recommended_only():
    assert resolve_targets("recommended") == ("recommended",)


def test_unknown_raises():
    import pytest
    with pytest.raises(ValueError):
        resolve_targets("nope")
