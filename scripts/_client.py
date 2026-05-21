"""Shared helpers: venv bootstrap, config, Plex connection."""
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_DIR / ".venv"
VENV_PY = VENV_DIR / "bin" / "python"
CONFIG_DIR = Path.home() / ".config" / "plex-collection-manager"
CONFIG_FILE = CONFIG_DIR / "config.json"
EXEMPTIONS_FILE = CONFIG_DIR / "exemptions.json"
REQUIREMENTS = SKILL_DIR / "requirements.txt"


def ensure_venv():
    """Create .venv (without ensurepip) and install requirements via host pip.

    Re-exec into the venv interpreter if we are not already running in it.
    """
    # NOTE: compare the *unresolved* interpreter paths. On this machine the
    # venv's bin/python is a symlink to the system interpreter, so .resolve()
    # would make the host python3 and VENV_PY look identical and we would
    # never re-exec (breaking the second/idempotent run).
    if Path(sys.executable) == VENV_PY:
        return  # already inside the venv

    if not VENV_PY.exists():
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(VENV_DIR)],
            check=True,
        )
    # Install requirements into the venv using the host pip's --python flag.
    subprocess.run(
        [sys.executable, "-m", "pip", "--python", str(VENV_PY),
         "install", "-q", "-r", str(REQUIREMENTS)],
        check=True,
    )
    # Re-exec inside the venv so `import plexapi` works.
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])


def load_config():
    """Return the saved config dict, or raise a clear error if absent."""
    if not CONFIG_FILE.exists():
        raise SystemExit(
            "Not authenticated. Run: python3 scripts/auth.py"
        )
    return json.loads(CONFIG_FILE.read_text())


def save_config(config):
    """Write config 0600 so the token is not world-readable."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    os.chmod(CONFIG_FILE, 0o600)


def load_exempt_keys():
    """Return the set of ratingKeys the user marked 'keep both'."""
    if not EXEMPTIONS_FILE.exists():
        return set()
    data = json.loads(EXEMPTIONS_FILE.read_text())
    return set(str(k) for k in data.get("ratingKeys", []))


def add_exempt_key(rating_key):
    """Add a ratingKey to the exemptions file (idempotent)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"ratingKeys": [], "rules": []}
    if EXEMPTIONS_FILE.exists():
        data.update(json.loads(EXEMPTIONS_FILE.read_text()))
    keys = set(str(k) for k in data.get("ratingKeys", []))
    keys.add(str(rating_key))
    data["ratingKeys"] = sorted(keys)
    EXEMPTIONS_FILE.write_text(json.dumps(data, indent=2))
    os.chmod(EXEMPTIONS_FILE, 0o600)


def plex_headers():
    """Required X-Plex-* identity headers; client_id is created on first auth."""
    return {
        "X-Plex-Product": "Plex Collection Manager",
        "X-Plex-Version": "1.0",
        "X-Plex-Device": "Claude Code",
        "X-Plex-Platform": "Python",
    }


# Bounded per-request timeout (seconds). Without this, PlexServer uses a long
# default and can HANG when the server advertises an unreachable connection URL,
# even though the saved LAN URL responds in milliseconds. Keep it generous enough
# for big library listings but short enough to fail fast on a dead route.
CONNECT_TIMEOUT = 30


def connect():
    """Return a connected PlexServer using the saved token + base URL."""
    import requests
    from plexapi.server import PlexServer
    cfg = load_config()
    session = requests.Session()
    try:
        return PlexServer(cfg["server_baseurl"], cfg["token"],
                          session=session, timeout=CONNECT_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 - surface a usable message
        raise SystemExit(
            f"Could not reach Plex at {cfg['server_baseurl']}: {exc}\n"
            "If the token expired, re-run: python3 scripts/auth.py"
        )


PENDING_FILE = CONFIG_DIR / "pending_pin.json"
AUDIT_FILE = CONFIG_DIR / "audit.log"
MANIFEST_FILE = CONFIG_DIR / "collections.json"


def save_pending(data):
    """Persist in-progress PIN login state (0600). Internal to auth split flow."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(data, indent=2))
    os.chmod(PENDING_FILE, 0o600)


def load_pending():
    """Return saved pending PIN state, or None if none (it is optional state,
    unlike load_config which errors when the required config is absent)."""
    if not PENDING_FILE.exists():
        return None
    return json.loads(PENDING_FILE.read_text())


def clear_pending():
    """Delete the pending PIN state if present (idempotent)."""
    PENDING_FILE.unlink(missing_ok=True)


def server_name(server):
    """Friendly name of a connected PlexServer for audit records ('?' if absent)."""
    return getattr(server, "friendlyName", None) or "?"


def audit(action, **fields):
    """Append one JSON line recording a server-modifying action (append-only).

    Records a timestamp + action + any provided fields (e.g. server, ratingKey,
    title, file, size, old, new). Never rewrites existing history. Best-effort:
    an audit failure must never block or crash the action it records.
    """
    record = {"ts": datetime.datetime.now().astimezone().isoformat(),
              "action": action}
    record.update(fields)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass  # auditing is best-effort; never break the real operation


def load_manifest():
    """Return the list of recorded rule-based collections, or [] if none."""
    if not MANIFEST_FILE.exists():
        return []
    return json.loads(MANIFEST_FILE.read_text())


def record_collection(entry):
    """Upsert a manifest entry (keyed by ratingKey). entry: dict with at least
    name, ratingKey, section, criteria. Used by smartbuild/resync to remember
    the rule behind a collection so it can be kept up to date."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = load_manifest()
    data = [e for e in data if str(e.get("ratingKey")) != str(entry.get("ratingKey"))]
    data.append(entry)
    MANIFEST_FILE.write_text(json.dumps(data, indent=2))
    os.chmod(MANIFEST_FILE, 0o600)


if __name__ == "__main__":
    ensure_venv()
    print(f"Running in: {sys.executable}")
    import plexapi
    print(f"plexapi {plexapi.__version__}")
