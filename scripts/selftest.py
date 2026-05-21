"""Read-only connectivity self-test: verify auth + server reachability."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _client


def run():
    cfg = _client.load_config()
    print(f"Config: {_client.CONFIG_FILE}")
    print(f"Configured server: {cfg.get('server_name', '?')}")
    print(f"Base URL: {cfg.get('server_baseurl', '?')}")

    print("\nConnecting...")
    server = _client.connect()
    name = getattr(server, "friendlyName", None) or "?"
    version = getattr(server, "version", None) or "?"
    user = getattr(server, "myPlexUsername", None) or "?"
    print(f"  Connected to '{name}' (Plex Media Server {version})")
    print(f"  Authenticated as: {user}")

    sections = server.library.sections()
    print(f"\nLibraries ({len(sections)}):")
    for s in sections:
        print(f"  - {s.title} ({s.type})")

    print("\nSelf-test OK: authentication and server connection are working.")


def main():
    _client.ensure_venv()
    run()


if __name__ == "__main__":
    main()
