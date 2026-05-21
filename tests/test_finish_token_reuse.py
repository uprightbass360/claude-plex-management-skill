"""finish() must reuse an already-claimed token (a PIN is single-use), so a
multi-server selection retry doesn't try to re-claim a spent PIN.

Note: auth.py does `import _client` (flat name via its path shim), so the module
it uses is `auth._client`. Patch THAT object — not `scripts._client`, which is a
distinct module instance under the package import path.
"""
import pytest
from scripts import auth

_client = auth._client  # the exact module instance auth.py operates on


class _FakeServer:
    def __init__(self, name):
        self.name = name


def _seed_pending(monkeypatch, tmp_path, **extra):
    """Point _client at a temp pending file and write base pending state."""
    monkeypatch.setattr(_client, "PENDING_FILE", tmp_path / "pending.json")
    monkeypatch.setattr(_client, "CONFIG_DIR", tmp_path)
    data = {"client_id": "cid", "pin_id": "1", "pin_code": "ABCD"}
    data.update(extra)
    _client.save_pending(data)


def test_finish_reuses_existing_token_without_touching_pin(monkeypatch, tmp_path):
    # Pending already carries a token (a prior finish claimed it, then stopped to
    # ask which server). A retry must NOT re-claim the spent PIN.
    _seed_pending(monkeypatch, tmp_path, token="TKN")

    def _boom(_cid):
        raise AssertionError("must not rebuild MyPlexPinLogin when token exists")

    monkeypatch.setattr(auth, "_pin_login", _boom)
    monkeypatch.setattr(auth, "_discover_servers",
                        lambda token: [_FakeServer("Marvin")])
    saved = {}
    monkeypatch.setattr(auth, "_save_for_server",
                        lambda s, cid, tok: saved.update(name=s.name, token=tok))

    auth.finish(server_name="Marvin")
    assert saved == {"name": "Marvin", "token": "TKN"}


def test_finish_multi_server_persists_token_then_retry_succeeds(monkeypatch, tmp_path):
    # First call: token claimed from PIN, multiple servers -> exits asking for
    # --server, but the token is persisted into pending.
    _seed_pending(monkeypatch, tmp_path)

    class _FakePinLogin:
        def __init__(self):
            self._id = None
            self._code = None
            self.token = None

        def checkLogin(self):
            self.token = "TKN"
            return True

    monkeypatch.setattr(auth, "_pin_login", lambda _cid: _FakePinLogin())
    monkeypatch.setattr(auth, "_discover_servers",
                        lambda token: [_FakeServer("Marvin"), _FakeServer("noodflix")])
    saved = {}
    monkeypatch.setattr(auth, "_save_for_server",
                        lambda s, cid, tok: saved.update(name=s.name, token=tok))

    with pytest.raises(SystemExit):
        auth.finish()  # ambiguous: multiple servers, no --server

    # Token was persisted so the retry can reuse it.
    assert _client.load_pending().get("token") == "TKN"

    # Retry with --server now: must NOT rebuild the (spent) PIN login.
    monkeypatch.setattr(auth, "_pin_login",
                        lambda _cid: (_ for _ in ()).throw(
                            AssertionError("retry must reuse persisted token")))
    auth.finish(server_name="Marvin")
    assert saved == {"name": "Marvin", "token": "TKN"}
    # On success, pending is cleared.
    assert _client.load_pending() is None
