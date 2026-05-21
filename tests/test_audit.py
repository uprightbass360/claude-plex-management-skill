import json
from scripts import _client as h


def test_audit_appends_one_json_line_with_core_fields(tmp_path, monkeypatch):
    log = tmp_path / "audit.log"
    monkeypatch.setattr(h, "AUDIT_FILE", log)
    monkeypatch.setattr(h, "CONFIG_DIR", tmp_path)
    h.audit("delete_version", server="Marvin", ratingKey="42", title="X")
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["action"] == "delete_version"
    assert rec["server"] == "Marvin"
    assert rec["ratingKey"] == "42"
    assert rec["title"] == "X"
    assert "ts" in rec and rec["ts"]  # ISO timestamp present


def test_audit_is_append_only(tmp_path, monkeypatch):
    log = tmp_path / "audit.log"
    monkeypatch.setattr(h, "AUDIT_FILE", log)
    monkeypatch.setattr(h, "CONFIG_DIR", tmp_path)
    h.audit("a", server="S")
    h.audit("b", server="S")
    lines = log.read_text().splitlines()
    assert [json.loads(l)["action"] for l in lines] == ["a", "b"]


def test_audit_creates_dir_if_missing(tmp_path, monkeypatch):
    nested = tmp_path / "sub"
    monkeypatch.setattr(h, "AUDIT_FILE", nested / "audit.log")
    monkeypatch.setattr(h, "CONFIG_DIR", nested)
    h.audit("x", server="S")
    assert (nested / "audit.log").exists()
