"""Authenticate to Plex via the PIN OAuth flow.

No-arg / `interactive`: blocking flow (prints code, waits, saves token).
`start`: generate a PIN, print the code+link, persist pending state, return now.
`finish [--server NAME]`: claim the token after the user authorized in a browser.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import uuid

import _client


def _pin_login(client_id):
    """Build a MyPlexPinLogin carrying our stable client identifier."""
    from plexapi.myplex import MyPlexPinLogin
    headers = _client.plex_headers()
    headers["X-Plex-Client-Identifier"] = client_id
    return MyPlexPinLogin(headers=headers, oauth=False)


def _client_id_from_config():
    """Reuse an existing client id if we have one, else mint a new uuid4."""
    try:
        cfg = _client.load_config()
    except SystemExit:
        cfg = {}
    return cfg.get("client_id") or str(uuid.uuid4())


def _discover_servers(token):
    from plexapi.myplex import MyPlexAccount
    account = MyPlexAccount(token=token)
    return [r for r in account.resources() if "server" in r.provides]


def _save_for_server(server, client_id, token):
    connection = server.connect()  # PlexServer; ._baseurl is the saved base URL
    _client.save_config({
        "token": token,
        "client_id": client_id,
        "server_name": server.name,
        "server_baseurl": connection._baseurl,
    })
    print(f"\nAuthenticated. Saved server '{server.name}'.")
    print(f"Config: {_client.CONFIG_FILE}")


def _print_pin(code):
    print("To authorize, open https://plex.tv/link and enter this code:")
    print(f"\n    {code}\n")


# ---- interactive (blocking) ----

def login():
    client_id = _client_id_from_config()
    pinlogin = _pin_login(client_id)
    _print_pin(pinlogin.pin)
    print("Waiting for authorization (Ctrl-C to cancel)...")
    pinlogin.run(timeout=300)
    pinlogin.waitForLogin()
    if not pinlogin.token:
        raise SystemExit("Authorization failed or timed out.")
    servers = _discover_servers(pinlogin.token)
    if not servers:
        raise SystemExit("No Plex servers found on this account.")
    return servers, client_id, pinlogin.token


def choose_server(servers):
    if len(servers) == 1:
        return servers[0]
    print("\nMultiple servers found:")
    for i, s in enumerate(servers, 1):
        print(f"  {i}. {s.name}")
    idx = int(input("Choose a server number: ")) - 1
    return servers[idx]


def interactive():
    servers, client_id, token = login()
    server = choose_server(servers)
    _save_for_server(server, client_id, token)


# ---- split (non-blocking) ----

def start():
    # plexapi's MyPlexPinLogin has no public API for a resumable/split flow, so
    # we read the private _id/_code it sets and persist them; finish() restores
    # them onto a fresh instance to claim the token. Don't "fix" this to a public
    # call — there isn't one in plexapi 4.18.1.
    client_id = _client_id_from_config()
    pinlogin = _pin_login(client_id)
    code = pinlogin.pin  # accessing .pin triggers PIN creation; sets _id and _code
    _client.save_pending({
        "client_id": client_id,
        "pin_id": pinlogin._id,
        "pin_code": pinlogin._code,
    })
    _print_pin(code)
    print("Then run: python3 scripts/auth.py finish")


def finish(server_name=None):
    pending = _client.load_pending()
    if not pending:
        raise SystemExit("No pending login. Run: python3 scripts/auth.py start")
    # A PIN is single-use. If a prior finish already claimed the token (e.g. it
    # stopped to ask which server), reuse that token instead of re-checking the
    # spent PIN — otherwise a multi-server retry would fail. We persist the token
    # into pending the moment we have it, and only clear pending once config is
    # saved for a chosen server.
    token = pending.get("token")
    if not token:
        # Restore the PIN id/code from start() onto a fresh instance (same client
        # id), then claim the token. See start() on why these are private attrs.
        pinlogin = _pin_login(pending["client_id"])
        pinlogin._id = pending["pin_id"]
        pinlogin._code = pending["pin_code"]
        if not pinlogin.checkLogin() or not pinlogin.token:
            raise SystemExit(
                "Not authorized yet (or the code expired). Authorize at "
                "https://plex.tv/link with the code from `start`, then re-run "
                "finish. If it expired, run `start` again."
            )
        token = pinlogin.token
        pending["token"] = token
        _client.save_pending(pending)  # survive a server-selection retry
    servers = _discover_servers(token)
    if not servers:
        raise SystemExit("No Plex servers found on this account.")
    # Non-interactive selection (unlike interactive's choose_server): require
    # --server when there's more than one, since finish() can't prompt.
    if server_name:
        match = [s for s in servers if s.name == server_name]
        if not match:
            names = ", ".join(s.name for s in servers)
            raise SystemExit(f"No server named '{server_name}'. Found: {names}")
        server = match[0]
    elif len(servers) == 1:
        server = servers[0]
    else:
        names = "\n".join(f"  - {s.name}" for s in servers)
        raise SystemExit(
            "Multiple servers found; re-run with --server:\n" + names +
            "\n\n  python3 scripts/auth.py finish --server \"<name>\""
        )
    _save_for_server(server, pending["client_id"], token)
    _client.clear_pending()


def main():
    _client.ensure_venv()
    p = argparse.ArgumentParser(description="Authenticate to Plex.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("interactive", help="Blocking flow (default).")
    sub.add_parser("start", help="Generate a PIN and return immediately.")
    pf = sub.add_parser("finish", help="Claim the token after authorizing.")
    pf.add_argument("--server", help="Server name (if you have more than one).")
    args = p.parse_args()

    if args.cmd == "start":
        start()
    elif args.cmd == "finish":
        finish(server_name=args.server)
    else:  # None or "interactive"
        interactive()


if __name__ == "__main__":
    main()
