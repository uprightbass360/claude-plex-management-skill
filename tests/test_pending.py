import json
from scripts import _client as h


def test_pending_roundtrip(tmp_path, monkeypatch):
    pending = tmp_path / "pending.json"
    monkeypatch.setattr(h, "PENDING_FILE", pending)
    monkeypatch.setattr(h, "CONFIG_DIR", tmp_path)
    h.save_pending({"pin_id": "1", "pin_code": "ABCD", "client_id": "cid"})
    assert h.load_pending() == {"pin_id": "1", "pin_code": "ABCD", "client_id": "cid"}
    # file is 0600
    assert (pending.stat().st_mode & 0o777) == 0o600


def test_load_pending_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "PENDING_FILE", tmp_path / "nope.json")
    assert h.load_pending() is None


def test_clear_pending_removes_file(tmp_path, monkeypatch):
    pending = tmp_path / "pending.json"
    monkeypatch.setattr(h, "PENDING_FILE", pending)
    monkeypatch.setattr(h, "CONFIG_DIR", tmp_path)
    h.save_pending({"pin_id": "1"})
    assert pending.exists()
    h.clear_pending()
    assert not pending.exists()
    # idempotent: clearing again does not raise
    h.clear_pending()
