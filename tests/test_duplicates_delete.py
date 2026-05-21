"""delete_versions must: delete ONLY explicitly-named ids, abort atomically if
any requested id is unknown (deleting nothing), and audit before each delete.
These guard the most destructive function in the codebase.
"""
import pytest
from scripts import duplicates

_client = duplicates._client


class _FakeMedia:
    def __init__(self, mid):
        self.id = mid
        self.deleted = False

    def delete(self):
        self.deleted = True


def _group(rating_key, title, versions):
    return {"ratingKey": rating_key, "title": title, "exempt": False,
            "versions": versions}


def _ver(media):
    return {"media_id": media.id, "resolution": "1080", "bitrate": 8000,
            "size": 1_000, "file": f"/m/{media.id}.mkv", "tag": "MAIN",
            "suggested_keeper": False, "_media": media}


def _patch(monkeypatch, tmp_path, groups, audited):
    """Stub scan_groups to return our fakes and capture audit calls."""
    monkeypatch.setattr(duplicates, "scan_groups", lambda server, section: groups)
    monkeypatch.setattr(_client, "server_name", lambda server: "Marvin")
    monkeypatch.setattr(_client, "audit",
                        lambda action, **f: audited.append((action, f)))


def test_delete_removes_only_named_ids(monkeypatch, tmp_path):
    keep, drop = _FakeMedia(11), _FakeMedia(12)
    groups = [_group("7", "Movie", [_ver(keep), _ver(drop)])]
    audited = []
    _patch(monkeypatch, tmp_path, groups, audited)

    duplicates.delete_versions(object(), "Movies", [12])

    assert drop.deleted is True
    assert keep.deleted is False                      # untouched
    assert [a for a, _ in audited] == ["delete_version"]
    assert audited[0][1]["media_id"] == 12


def test_delete_aborts_atomically_on_unknown_id(monkeypatch, tmp_path):
    a, b = _FakeMedia(11), _FakeMedia(12)
    groups = [_group("7", "Movie", [_ver(a), _ver(b)])]
    audited = []
    _patch(monkeypatch, tmp_path, groups, audited)

    # 12 is valid, 999 is not — the whole call must abort, deleting nothing.
    with pytest.raises(SystemExit):
        duplicates.delete_versions(object(), "Movies", [12, 999])

    assert a.deleted is False
    assert b.deleted is False                          # valid id NOT deleted
    assert audited == []                               # nothing audited


def test_delete_can_remove_the_suggested_keeper(monkeypatch, tmp_path):
    # Tags are advisory only: an explicit id always wins, even the keeper.
    keeper = _FakeMedia(11)
    v = _ver(keeper)
    v["suggested_keeper"] = True
    groups = [_group("7", "Movie", [v])]
    audited = []
    _patch(monkeypatch, tmp_path, groups, audited)

    duplicates.delete_versions(object(), "Movies", [11])
    assert keeper.deleted is True
