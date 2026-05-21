import json
from scripts import _client as h


def test_manifest_record_and_load(tmp_path, monkeypatch):
    mf = tmp_path / "collections.json"
    monkeypatch.setattr(h, "MANIFEST_FILE", mf)
    monkeypatch.setattr(h, "CONFIG_DIR", tmp_path)
    h.record_collection({"name": "80s Horror", "ratingKey": "21840",
                         "section": "Movies", "criteria": {"genre": "Horror", "decade": 1980}})
    data = h.load_manifest()
    assert len(data) == 1
    assert data[0]["name"] == "80s Horror"
    assert data[0]["criteria"] == {"genre": "Horror", "decade": 1980}


def test_manifest_upsert_by_rating_key(tmp_path, monkeypatch):
    mf = tmp_path / "collections.json"
    monkeypatch.setattr(h, "MANIFEST_FILE", mf)
    monkeypatch.setattr(h, "CONFIG_DIR", tmp_path)
    h.record_collection({"name": "X", "ratingKey": "1", "section": "Movies", "criteria": {"genre": "A"}})
    h.record_collection({"name": "X renamed", "ratingKey": "1", "section": "Movies", "criteria": {"genre": "B"}})
    data = h.load_manifest()
    assert len(data) == 1  # same ratingKey -> replaced, not duplicated
    assert data[0]["name"] == "X renamed"
    assert data[0]["criteria"] == {"genre": "B"}


def test_load_manifest_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "MANIFEST_FILE", tmp_path / "none.json")
    assert h.load_manifest() == []
