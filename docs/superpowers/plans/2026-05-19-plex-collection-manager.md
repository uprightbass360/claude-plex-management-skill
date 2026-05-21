# Plex Collection Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conversational Claude skill that authenticates to a Plex server via PIN OAuth and lets the user browse, organize collections/boxsets, edit metadata, and safely prune duplicate media versions.

**Architecture:** A `SKILL.md` instructs Claude when/how to use the skill. Small single-purpose Python scripts (`auth`, `browse`, `collections`, `metadata`, `duplicates`) share a `_client.py` that bootstraps an isolated venv, loads a stored token, and connects to the chosen server. Pure logic (keeper-ranking, exemption filtering, rule matching) lives in importable functions unit-tested with mocked plexapi objects. Secrets live outside the repo in `~/.config/plex-collection-manager/`.

**Tech Stack:** Python 3.12, python-plexapi 4.18.x, pytest. venv created with `--without-pip`; packages installed via the host user-pip using `python3 -m pip --python <venv>/bin/python install ...` (this machine lacks `ensurepip`).

---

## Environment Facts (verified against plexapi 4.18.1)

- `python3 -m venv --without-pip <venv>` works; plain `python3 -m venv <venv>` FAILS (no ensurepip).
- Host pip exists at user level. Install into a venv with: `python3 -m pip --python <venv>/bin/python install <pkg>` — the `--python` flag MUST come before the `install` subcommand.
- `from plexapi.myplex import MyPlexAccount, MyPlexPinLogin` — `MyPlexPinLogin(headers=..., oauth=False)` exposes `.pin`, `.run()`, `.waitForLogin()`, and `.token` after login.
- `MyPlexAccount(token=...).resources()` lists servers; `.connect()` on a resource returns a `PlexServer`.
- `PlexServer.library.sections()` → sections; `section.collections()`, `section.search(...)`, `section.search(duplicate=True)` for movie duplicates.
- A movie/episode has `.media` (list of `Media`). `Media.videoResolution` (str, e.g. "1080"), `Media.bitrate` (int), `Media.width`/`.height` (int). `Media.parts` (list of `MediaPart`); `MediaPart.size` (int bytes), `MediaPart.file` (str path). `Media.delete()` removes a single version; item `.delete()` removes the whole item.
- `Collection.addItems()`, `Collection.removeItems()`; `LibrarySection.createCollection(title, items=[...])`.
- `Movie.editTitle()`, `Movie.editSortTitle()`, `Movie.uploadPoster(url=...)`.

---

## File Structure

```
plex-collection-manager/
├── SKILL.md                  # when-to-use + workflow for Claude
├── requirements.txt          # plexapi==4.18.1
├── .gitignore                # .venv/, __pycache__, *.pyc
├── scripts/
│   ├── _client.py            # venv bootstrap, config load, connect, table helpers
│   ├── ranking.py            # PURE: keeper-ranking + exemption filtering + dup grouping
│   ├── rules.py              # PURE: collection auto-build rule matching
│   ├── auth.py               # PIN OAuth login → write config
│   ├── browse.py             # list sections/collections/items + version detail
│   ├── manage_collections.py # create/rename/delete/add/remove/order/auto-build
│                              # (NOT collections.py — that would shadow the
│                              #  stdlib `collections` module via the path shim,
│                              #  breaking functools/argparse in every script)
│   ├── metadata.py           # edit title/sort title/poster
│   └── duplicates.py         # find dups; dry-run report; --confirm to delete
└── tests/
    ├── conftest.py           # fake Media/MediaPart/Item factories
    ├── test_ranking.py
    └── test_rules.py
```

Pure logic (`ranking.py`, `rules.py`) is separated from plexapi I/O so it is unit-testable without a live server. CLI scripts are thin wrappers that call pure functions and print tables.

---

## Task 1: Project skeleton, gitignore, requirements

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `scripts/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create `requirements.txt`**

```
plexapi==4.18.1
pytest==8.3.4
```

- [ ] **Step 2: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create empty package markers**

Create `scripts/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt .gitignore scripts/__init__.py tests/__init__.py
git commit -m "chore: project skeleton, requirements, gitignore"
```

---

## Task 2: venv bootstrap helper (`_client.py` part 1)

**Files:**
- Create: `scripts/_client.py`

This task adds ONLY the venv bootstrap + a `main()` self-test that prints the python path. Config/connect come in Task 4.

- [ ] **Step 1: Write the bootstrap function**

Create `scripts/_client.py`:

```python
"""Shared helpers: venv bootstrap, config, Plex connection."""
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
    # Compare UNRESOLVED paths: the --without-pip venv's bin/python is a symlink
    # to the system python, so .resolve() would make both sides equal and the
    # guard would wrongly early-return on the 2nd run, skipping the re-exec.
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


if __name__ == "__main__":
    ensure_venv()
    print(f"Running in: {sys.executable}")
    import plexapi
    print(f"plexapi {plexapi.__version__}")
```

- [ ] **Step 2: Run the bootstrap end-to-end**

Run: `python3 scripts/_client.py`
Expected: first run creates `.venv/`, installs plexapi, re-execs, then prints `Running in: .../.venv/bin/python` and `plexapi 4.18.1`.

- [ ] **Step 3: Run again to confirm idempotence**

Run: `python3 scripts/_client.py`
Expected: same output, fast (venv already exists).

- [ ] **Step 4: Commit**

```bash
git add scripts/_client.py
git commit -m "feat: venv bootstrap that installs plexapi and re-execs"
```

---

## Task 3: Pure keeper-ranking + exemption logic (`ranking.py`) — TDD

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_ranking.py`
- Create: `scripts/ranking.py`

The pure functions operate on lightweight dicts so they need no plexapi. The CLI later adapts plexapi objects into these dicts.

- [ ] **Step 1: Write fake factories in `tests/conftest.py`**

```python
"""Plain-dict factories mirroring the shape ranking.py consumes."""


def make_version(resolution="1080", bitrate=8000, size=5_000_000_000,
                 file="/m/a.mkv"):
    """One media version as a plain dict (adapted from plexapi.Media)."""
    return {
        "resolution": resolution,
        "bitrate": bitrate,
        "size": size,
        "file": file,
    }


def make_item(rating_key="1", title="Movie", versions=None):
    """A duplicate-group item: one title with multiple versions."""
    return {
        "ratingKey": str(rating_key),
        "title": title,
        "versions": versions if versions is not None else [make_version()],
    }
```

- [ ] **Step 2: Write failing tests in `tests/test_ranking.py`**

```python
from tests.conftest import make_version, make_item
from scripts.ranking import resolution_rank, rank_versions, choose_keeper, plan_pruning


def test_resolution_rank_orders_known_values():
    assert resolution_rank("4k") > resolution_rank("1080")
    assert resolution_rank("1080") > resolution_rank("720")
    assert resolution_rank("720") > resolution_rank("sd")
    assert resolution_rank("unknown-label") == 0


def test_rank_versions_sorts_by_resolution_then_bitrate_then_size():
    v_lo = make_version(resolution="720", bitrate=3000, size=1_000)
    v_hi = make_version(resolution="1080", bitrate=8000, size=9_000)
    v_mid = make_version(resolution="1080", bitrate=8000, size=2_000)
    ranked = rank_versions([v_lo, v_hi, v_mid])
    assert ranked == [v_hi, v_mid, v_lo]  # 1080>720; tie→bitrate; tie→size


def test_choose_keeper_returns_top_ranked():
    v_lo = make_version(resolution="720")
    v_hi = make_version(resolution="4k")
    item = make_item(versions=[v_lo, v_hi])
    keeper, removals = choose_keeper(item)
    assert keeper is v_hi
    assert removals == [v_lo]


def test_plan_pruning_excludes_exempt_items():
    keep_me = make_item(rating_key="100", versions=[make_version("1080"),
                                                    make_version("720")])
    prune_me = make_item(rating_key="200", versions=[make_version("1080"),
                                                     make_version("720")])
    plan = plan_pruning([keep_me, prune_me], exempt_keys={"100"})
    assert [g["ratingKey"] for g in plan["prunable"]] == ["200"]
    assert [g["ratingKey"] for g in plan["exempt"]] == ["100"]
    assert len(plan["prunable"][0]["removals"]) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ranking.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.ranking'`.

(If pytest isn't found, run `python3 scripts/_client.py` once to build the venv.)

- [ ] **Step 4: Implement `scripts/ranking.py`**

```python
"""Pure duplicate-ranking and exemption logic. No plexapi imports."""

_RES_ORDER = {"4k": 5, "2160": 5, "1080": 4, "720": 3, "480": 2, "sd": 1}


def resolution_rank(resolution):
    """Map a Plex videoResolution label to a sortable integer (0 if unknown)."""
    if resolution is None:
        return 0
    return _RES_ORDER.get(str(resolution).lower(), 0)


def rank_versions(versions):
    """Sort versions best-first: resolution, then bitrate, then size (all desc)."""
    return sorted(
        versions,
        key=lambda v: (
            resolution_rank(v.get("resolution")),
            v.get("bitrate") or 0,
            v.get("size") or 0,
        ),
        reverse=True,
    )


def choose_keeper(item):
    """Return (keeper_version, [removal_versions]) for one duplicate group."""
    ranked = rank_versions(item["versions"])
    return ranked[0], ranked[1:]


def plan_pruning(items, exempt_keys=frozenset()):
    """Split duplicate items into prunable vs. exempt groups.

    Returns {"prunable": [...], "exempt": [...]}. Each prunable group has
    keeper + removals; exempt groups are reported but never get removals.
    """
    prunable, exempt = [], []
    for item in items:
        keeper, removals = choose_keeper(item)
        group = {
            "ratingKey": item["ratingKey"],
            "title": item["title"],
            "keeper": keeper,
            "removals": removals,
        }
        if item["ratingKey"] in exempt_keys:
            group["removals"] = []
            exempt.append(group)
        else:
            prunable.append(group)
    return {"prunable": prunable, "exempt": exempt}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ranking.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_ranking.py scripts/ranking.py
git commit -m "feat: pure keeper-ranking and exemption logic with tests"
```

---

## Task 4: Config + connection helpers (`_client.py` part 2)

**Files:**
- Modify: `scripts/_client.py` (append functions)

- [ ] **Step 1: Append config + connect helpers to `scripts/_client.py`**

Insert these functions ABOVE the `if __name__ == "__main__":` block:

```python
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


def connect():
    """Return a connected PlexServer using the saved token + base URL."""
    from plexapi.server import PlexServer
    cfg = load_config()
    try:
        return PlexServer(cfg["server_baseurl"], cfg["token"])
    except Exception as exc:  # noqa: BLE001 - surface a usable message
        raise SystemExit(
            f"Could not reach Plex at {cfg['server_baseurl']}: {exc}\n"
            "If the token expired, re-run: python3 scripts/auth.py"
        )
```

- [ ] **Step 2: Verify the module still imports**

Run: `.venv/bin/python -c "import scripts._client as c; print(c.CONFIG_FILE)"`
Expected: prints `.../.config/plex-collection-manager/config.json` with no error.

- [ ] **Step 3: Commit**

```bash
git add scripts/_client.py
git commit -m "feat: config, exemptions, and Plex connection helpers"
```

---

## Task 5: PIN OAuth login (`auth.py`)

**Files:**
- Create: `scripts/auth.py`

Live login can't be unit-tested without a real Plex account; this task is verified by import + a `--help`-style dry path. The full login is exercised manually by the user.

- [ ] **Step 1: Implement `scripts/auth.py`**

```python
"""Authenticate to Plex via the official PIN OAuth flow and save a token."""
import sys
import uuid

import _client


def login():
    from plexapi.myplex import MyPlexPinLogin, MyPlexAccount

    cfg = {}
    try:
        cfg = _client.load_config()
    except SystemExit:
        pass
    client_id = cfg.get("client_id") or str(uuid.uuid4())

    headers = _client.plex_headers()
    headers["X-Plex-Client-Identifier"] = client_id

    pinlogin = MyPlexPinLogin(headers=headers, oauth=False)
    print("To authorize, open https://plex.tv/link and enter this code:")
    print(f"\n    {pinlogin.pin}\n")
    print("Waiting for authorization (Ctrl-C to cancel)...")
    pinlogin.run(timeout=300)
    pinlogin.waitForLogin()
    if not pinlogin.token:
        raise SystemExit("Authorization failed or timed out.")

    account = MyPlexAccount(token=pinlogin.token)
    servers = [r for r in account.resources() if "server" in r.provides]
    if not servers:
        raise SystemExit("No Plex servers found on this account.")
    return account, servers, client_id, pinlogin.token


def choose_server(servers):
    if len(servers) == 1:
        return servers[0]
    print("\nMultiple servers found:")
    for i, s in enumerate(servers, 1):
        print(f"  {i}. {s.name}")
    idx = int(input("Choose a server number: ")) - 1
    return servers[idx]


def main():
    _client.ensure_venv()
    account, servers, client_id, token = login()
    server = choose_server(servers)
    connection = server.connect()  # PlexServer; .url(...) gives base
    _client.save_config({
        "token": token,
        "client_id": client_id,
        "server_name": server.name,
        "server_baseurl": connection._baseurl,
    })
    print(f"\nAuthenticated. Saved server '{server.name}'.")
    print(f"Config: {_client.CONFIG_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports and shows the PIN path without crashing on import**

Run: `.venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import auth; print('ok', hasattr(auth,'main'))"`
Expected: `ok True`.

- [ ] **Step 3: Manual live check (user-driven; note in output, do not block)**

Tell the user: run `python3 scripts/auth.py`, open the link, enter the code. Expected: "Authenticated. Saved server '<name>'." and a config file written 0600.

- [ ] **Step 4: Commit**

```bash
git add scripts/auth.py
git commit -m "feat: PIN OAuth login that discovers and saves a server"
```

---

## Task 6: Browse / inspect (`browse.py`)

**Files:**
- Create: `scripts/browse.py`

- [ ] **Step 1: Implement `scripts/browse.py`**

```python
"""Read-only listing of libraries, collections, items, and version detail."""
import argparse
import sys

import _client


def _fmt_size(num):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.1f}{unit}"
        num /= 1024


def list_sections(server):
    for s in server.library.sections():
        print(f"[{s.key}] {s.title} ({s.type}) — {s.totalSize} items")


def list_collections(server, section_title):
    section = server.library.section(section_title)
    cols = section.collections()
    if not cols:
        print(f"No collections in '{section_title}'.")
        return
    for c in cols:
        print(f"[{c.ratingKey}] {c.title} — {c.childCount} items")


def list_items(server, section_title, limit):
    section = server.library.section(section_title)
    for item in section.all()[:limit]:
        print(f"[{item.ratingKey}] {item.title} ({getattr(item,'year','?')})")


def show_item(server, rating_key):
    item = server.fetchItem(int(rating_key))
    print(f"{item.title} ({getattr(item,'year','?')})  ratingKey={item.ratingKey}")
    for m in item.media:
        size = sum((p.size or 0) for p in m.parts)
        files = ", ".join(p.file for p in m.parts if p.file)
        print(f"  - {m.videoResolution}  {m.bitrate}kbps  {_fmt_size(size)}")
        print(f"      {files}")


def main():
    _client.ensure_venv()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sections")
    pc = sub.add_parser("collections"); pc.add_argument("section")
    pi = sub.add_parser("items"); pi.add_argument("section"); pi.add_argument("--limit", type=int, default=50)
    ps = sub.add_parser("item"); ps.add_argument("rating_key")
    args = p.parse_args()

    server = _client.connect()
    if args.cmd == "sections":
        list_sections(server)
    elif args.cmd == "collections":
        list_collections(server, args.section)
    elif args.cmd == "items":
        list_items(server, args.section, args.limit)
    elif args.cmd == "item":
        show_item(server, args.rating_key)


if __name__ == "__main__":
    main()
```

Note: `auth.py` and the other scripts import `_client` directly, so each script must run from the `scripts/` dir or insert it on the path. Add the path shim at the top of every script as in Step 2.

- [ ] **Step 2: Add a path shim so scripts run from anywhere**

At the very top of `scripts/browse.py` (and apply the same two lines to `auth.py`, `manage_collections.py`, `metadata.py`, `duplicates.py` as they are created), before `import _client`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

- [ ] **Step 3: Verify import**

Run: `.venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import browse; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Manual live check**

Tell the user: `python3 scripts/browse.py sections` should list their libraries (requires Task 5 auth done).

- [ ] **Step 5: Commit**

```bash
git add scripts/browse.py
git commit -m "feat: read-only browse of sections, collections, items, versions"
```

---

## Task 7: Auto-build rule matching (`rules.py`) — TDD

**Files:**
- Create: `tests/test_rules.py`
- Create: `scripts/rules.py`

Pure matching over item dicts so it is testable without plexapi.

- [ ] **Step 1: Write failing tests in `tests/test_rules.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.rules'`.

- [ ] **Step 3: Implement `scripts/rules.py`**

```python
"""Pure matching for auto-building collections. No plexapi imports."""


def match_items(items, criteria):
    """Return items matching criteria.

    criteria keys:
      - "titles": list of exact titles to include
      - any other key: exact-match against that field on the item
    Empty criteria matches nothing (avoids accidental whole-library grouping).
    """
    if not criteria:
        return []
    titles = set(criteria.get("titles", []))
    field_filters = {k: v for k, v in criteria.items() if k != "titles"}

    out = []
    for item in items:
        if titles and item.get("title") in titles:
            out.append(item)
            continue
        if field_filters and all(
            item.get(k) == v for k, v in field_filters.items()
        ):
            out.append(item)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_rules.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_rules.py scripts/rules.py
git commit -m "feat: pure auto-build rule matching with tests"
```

---

## Task 8: Collections management (`manage_collections.py`)

> NOTE: This file MUST be named `manage_collections.py`, not `collections.py`.
> Each script puts `scripts/` first on `sys.path` (the shim), so a file named
> `collections.py` would shadow Python's stdlib `collections` module — which
> `functools` imports — and break `argparse` in every script in the directory.

**Files:**
- Create: `scripts/manage_collections.py`

- [ ] **Step 1: Implement `scripts/manage_collections.py`**

```python
"""Create, edit, and auto-build collections/boxsets."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse

import _client
import rules


def create(server, section_title, name, rating_keys):
    section = server.library.section(section_title)
    items = [server.fetchItem(int(k)) for k in rating_keys]
    section.createCollection(title=name, items=items)
    print(f"Created collection '{name}' with {len(items)} items.")


def add(server, rating_key, item_keys):
    col = server.fetchItem(int(rating_key))
    items = [server.fetchItem(int(k)) for k in item_keys]
    col.addItems(items)
    print(f"Added {len(items)} items to '{col.title}'.")


def remove(server, rating_key, item_keys):
    col = server.fetchItem(int(rating_key))
    items = [server.fetchItem(int(k)) for k in item_keys]
    col.removeItems(items)
    print(f"Removed {len(items)} items from '{col.title}'.")


def rename(server, rating_key, new_title):
    col = server.fetchItem(int(rating_key))
    col.editTitle(new_title)
    print(f"Renamed collection to '{new_title}'.")


def delete(server, rating_key):
    col = server.fetchItem(int(rating_key))
    title = col.title
    col.delete()
    print(f"Deleted collection '{title}'.")


def autobuild(server, section_title, name, field, value, dry_run):
    section = server.library.section(section_title)
    items = [
        {"ratingKey": str(i.ratingKey), "title": i.title,
         field: getattr(i, field, None)}
        for i in section.all()
    ]
    matched = rules.match_items(items, {field: value})
    print(f"{len(matched)} items match {field}={value}:")
    for m in matched:
        print(f"  [{m['ratingKey']}] {m['title']}")
    if dry_run:
        print("\n(dry-run) Re-run with --apply to create the collection.")
        return
    plex_items = [server.fetchItem(int(m["ratingKey"])) for m in matched]
    section.createCollection(title=name, items=plex_items)
    print(f"Created '{name}' with {len(plex_items)} items.")


def main():
    _client.ensure_venv()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("create")
    pc.add_argument("section"); pc.add_argument("name")
    pc.add_argument("rating_keys", nargs="+")

    pa = sub.add_parser("add")
    pa.add_argument("rating_key"); pa.add_argument("item_keys", nargs="+")

    pr = sub.add_parser("remove")
    pr.add_argument("rating_key"); pr.add_argument("item_keys", nargs="+")

    pn = sub.add_parser("rename")
    pn.add_argument("rating_key"); pn.add_argument("new_title")

    pd = sub.add_parser("delete"); pd.add_argument("rating_key")

    pb = sub.add_parser("autobuild")
    pb.add_argument("section"); pb.add_argument("name")
    pb.add_argument("field"); pb.add_argument("value")
    pb.add_argument("--apply", action="store_true")

    args = p.parse_args()
    server = _client.connect()
    if args.cmd == "create":
        create(server, args.section, args.name, args.rating_keys)
    elif args.cmd == "add":
        add(server, args.rating_key, args.item_keys)
    elif args.cmd == "remove":
        remove(server, args.rating_key, args.item_keys)
    elif args.cmd == "rename":
        rename(server, args.rating_key, args.new_title)
    elif args.cmd == "delete":
        delete(server, args.rating_key)
    elif args.cmd == "autobuild":
        autobuild(server, args.section, args.name, args.field, args.value,
                  dry_run=not args.apply)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "import importlib.util; spec=importlib.util.spec_from_file_location('plexcm_mc','scripts/manage_collections.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('ok', all(hasattr(m,f) for f in ('create','add','remove','rename','delete','autobuild','main')))"`
Expected: `ok True`. (Load by file path, not `import collections` — that name resolves to the stdlib module.)

- [ ] **Step 3: Manual live check**

Tell the user: `python3 scripts/manage_collections.py autobuild Movies "Nolan Films" director Nolan` should preview matches (dry-run); add `--apply` to create.

- [ ] **Step 4: Commit**

```bash
git add scripts/manage_collections.py
git commit -m "feat: collection create/edit and rule-based auto-build"
```

---

## Task 9: Metadata / artwork (`metadata.py`)

**Files:**
- Create: `scripts/metadata.py`

- [ ] **Step 1: Implement `scripts/metadata.py`**

```python
"""Edit basic item metadata: title, sort title, poster."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse

import _client


def set_title(server, rating_key, value):
    item = server.fetchItem(int(rating_key))
    old = item.title
    item.editTitle(value)
    print(f"Title: '{old}' -> '{value}'")


def set_sort_title(server, rating_key, value):
    item = server.fetchItem(int(rating_key))
    item.editSortTitle(value)
    print(f"Sort title set to '{value}' for '{item.title}'.")


def set_poster(server, rating_key, url):
    item = server.fetchItem(int(rating_key))
    item.uploadPoster(url=url)
    print(f"Poster updated for '{item.title}'.")


def main():
    _client.ensure_venv()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pt = sub.add_parser("title"); pt.add_argument("rating_key"); pt.add_argument("value")
    ps = sub.add_parser("sort-title"); ps.add_argument("rating_key"); ps.add_argument("value")
    pp = sub.add_parser("poster"); pp.add_argument("rating_key"); pp.add_argument("url")
    args = p.parse_args()

    server = _client.connect()
    if args.cmd == "title":
        set_title(server, args.rating_key, args.value)
    elif args.cmd == "sort-title":
        set_sort_title(server, args.rating_key, args.value)
    elif args.cmd == "poster":
        set_poster(server, args.rating_key, args.url)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import metadata; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add scripts/metadata.py
git commit -m "feat: edit title, sort title, and poster"
```

---

## Task 10: Duplicate detection & safe pruning (`duplicates.py`)

**Files:**
- Create: `scripts/duplicates.py`

Pure ranking is already tested (Task 3). This script adapts plexapi objects into the dict shape and enforces the dry-run/confirm safety model.

- [ ] **Step 1: Implement `scripts/duplicates.py`**

```python
"""Find duplicate movie versions and prune safely (dry-run by default)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse

import _client
import ranking


def _fmt_size(num):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.1f}{unit}"
        num /= 1024


def _adapt(item):
    """Convert a plexapi item with multiple media into the ranking dict shape."""
    versions = []
    for m in item.media:
        size = sum((p.size or 0) for p in m.parts)
        file = next((p.file for p in m.parts if p.file), "")
        versions.append({
            "resolution": m.videoResolution,
            "bitrate": m.bitrate or 0,
            "size": size,
            "file": file,
            "_media": m,  # keep handle for deletion
        })
    return {"ratingKey": str(item.ratingKey), "title": item.title,
            "versions": versions}


def find_duplicates(server, section_title):
    section = server.library.section(section_title)
    dupes = [i for i in section.search(duplicate=True) if len(i.media) > 1]
    return [_adapt(i) for i in dupes]


def print_plan(plan):
    for group in plan["exempt"]:
        print(f"[KEEP BOTH] {group['title']} (ratingKey={group['ratingKey']}) "
              f"— {len(group['keeper']) if False else ''}intentional duplicate")
    for group in plan["prunable"]:
        keeper = group["keeper"]
        print(f"\n{group['title']} (ratingKey={group['ratingKey']})")
        print(f"  KEEP    {keeper['resolution']} {keeper['bitrate']}kbps "
              f"{_fmt_size(keeper['size'])}  {keeper['file']}")
        for r in group["removals"]:
            print(f"  REMOVE  {r['resolution']} {r['bitrate']}kbps "
                  f"{_fmt_size(r['size'])}  {r['file']}")


def apply_pruning(plan):
    removed = 0
    for group in plan["prunable"]:
        for r in group["removals"]:
            r["_media"].delete()
            removed += 1
    print(f"\nDeleted {removed} duplicate versions "
          "(Plex moves files to its trash, not a permanent wipe).")


def main():
    _client.ensure_venv()
    p = argparse.ArgumentParser()
    p.add_argument("section")
    p.add_argument("--confirm", action="store_true",
                   help="Actually delete the REMOVE versions. Default is dry-run.")
    args = p.parse_args()

    server = _client.connect()
    items = find_duplicates(server, args.section)
    exempt = _client.load_exempt_keys()
    plan = ranking.plan_pruning(items, exempt_keys=exempt)

    if not plan["prunable"] and not plan["exempt"]:
        print(f"No multi-version duplicates found in '{args.section}'.")
        return

    print_plan(plan)
    if not args.confirm:
        print("\n(dry-run) Nothing deleted. Re-run with --confirm to delete the "
              "REMOVE versions. To keep a group, add its ratingKey to exemptions.")
        return
    apply_pruning(plan)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import duplicates; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Run all unit tests (ranking still green)**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: all tests pass (7 total: 4 ranking + 3 rules).

- [ ] **Step 4: Manual live check**

Tell the user: `python3 scripts/duplicates.py Movies` shows a dry-run KEEP/REMOVE report; only `--confirm` deletes.

- [ ] **Step 5: Commit**

```bash
git add scripts/duplicates.py
git commit -m "feat: duplicate detection with dry-run report and confirm-to-delete"
```

---

## Task 11: SKILL.md — the conversational interface

**Files:**
- Create: `SKILL.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: plex-collection-manager
description: Use when the user wants to connect to their Plex server to browse libraries, organize collections/boxsets, edit media metadata, or find and prune duplicate content. Handles PIN-based Plex authentication and stores a token for reuse.
---

# Plex Collection Manager

Operate a user's Plex Media Server: authenticate, browse, organize collections,
edit metadata, and safely prune duplicate versions. All operations run through
Python scripts in `scripts/` that auto-bootstrap an isolated venv.

## First use: authenticate

If `~/.config/plex-collection-manager/config.json` does not exist, the user is
not authenticated. Run:

    python3 scripts/auth.py

Relay the printed code and `https://plex.tv/link` URL to the user and wait. The
script discovers their server(s), asks which to use if there are several, and
saves a token (file mode 0600). Never print the token.

## Browsing (read-only — safe to run freely)

- `python3 scripts/browse.py sections` — list libraries
- `python3 scripts/browse.py collections "<Section>"` — list collections
- `python3 scripts/browse.py items "<Section>" --limit N` — list items
- `python3 scripts/browse.py item <ratingKey>` — show versions, sizes, files

## Organizing collections / boxsets

- Create: `python3 scripts/manage_collections.py create "<Section>" "<Name>" <ratingKey>...`
- Add/remove: `python3 scripts/manage_collections.py add|remove <collectionKey> <itemKey>...`
- Rename: `python3 scripts/manage_collections.py rename <collectionKey> "<New Title>"`
- Delete: `python3 scripts/manage_collections.py delete <collectionKey>`
- Auto-build (dry-run): `python3 scripts/manage_collections.py autobuild "<Section>" "<Name>" <field> "<value>"`
  add `--apply` to create. Example field/value: `director Nolan`, `genre Sci-Fi`.

Echo what will change before applying. For delete and bulk operations, confirm
with the user first.

## Metadata

- `python3 scripts/metadata.py title <ratingKey> "<New Title>"`
- `python3 scripts/metadata.py sort-title <ratingKey> "<Sort Title>"`
- `python3 scripts/metadata.py poster <ratingKey> "<image-url>"`

## Pruning duplicates (DESTRUCTIVE — follow this discipline)

1. ALWAYS run the dry-run first and show the user the KEEP/REMOVE report:

       python3 scripts/duplicates.py "<Section>"

   Keeper is chosen by resolution → bitrate → file size. Items the user marked
   "keep both" appear as KEEP BOTH and are never deleted.

2. If the user wants to keep a specific group's duplicates, add its ratingKey to
   exemptions before deleting. Edit
   `~/.config/plex-collection-manager/exemptions.json` (a `ratingKeys` list) or
   use `_client.add_exempt_key()`.

3. ONLY after the user explicitly approves a specific batch, run with `--confirm`:

       python3 scripts/duplicates.py "<Section>" --confirm

   State clearly that Plex routes deleted files to its trash, not a hard wipe.
   Never pass `--confirm` on your own initiative.

## Notes

- The first script run creates `.venv/` and installs plexapi; this is expected.
- If a script reports "Not authenticated", run `scripts/auth.py`.
- If the server is unreachable, the error shows the URL tried; the token may have
  expired — re-run auth.
```

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "docs: SKILL.md conversational interface and safety rules"
```

---

## Task 12: Install the skill so Claude can discover it

**Files:**
- Create: symlink or copy at `~/.claude/skills/plex-collection-manager`

- [ ] **Step 1: Link the skill into the personal skills directory**

```bash
mkdir -p ~/.claude/skills
ln -sfn /home/upb/src/plex-collection-manager ~/.claude/skills/plex-collection-manager
ls -l ~/.claude/skills/plex-collection-manager
```

Expected: a symlink pointing at the repo.

- [ ] **Step 2: Sanity-check the whole suite once more**

Run: `.venv/bin/python -m pytest tests/ -v && for s in browse manage_collections metadata duplicates; do .venv/bin/python scripts/$s.py --help >/dev/null && echo "$s ok"; done && .venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import auth; print('auth ok')"`
Expected: all tests pass; each argparse script prints its usage (so `$s ok`); `auth ok`. (Don't `import collections` — that's the stdlib; the script is `manage_collections.py` and is exercised via `--help`.)

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: install skill into ~/.claude/skills"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Auth (PIN OAuth, token storage 0600, server discovery) → Task 5 + `_client` Task 4. ✓
- Browse/inspect with version detail → Task 6. ✓
- Create/edit collections + auto-build by rule → Tasks 7–8. ✓
- Metadata/artwork → Task 9. ✓
- Duplicate scope (Plex multi-version), keeper ranking res→bitrate→size, dry-run default, --confirm to delete, trash-not-wipe messaging → Tasks 3 + 10. ✓
- Exemptions ("keep both") excluded from delete set → Tasks 4 (storage) + 3 (filter) + 10 (report). ✓
- venv bootstrap (no ensurepip; `--python` host pip) → Task 2. ✓
- TDD for pure logic with mocked objects → Tasks 3, 7. ✓
- Config/secrets outside repo, .gitignore → Tasks 1, 4. ✓
- SKILL.md when-to-use + safety discipline → Task 11. ✓
- Skill discoverable by Claude → Task 12. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; every command has expected output. ✓

**Type consistency:** Dict shape `{ratingKey, title, versions:[{resolution,bitrate,size,file}]}` is identical across `ranking.py`, tests, and `duplicates._adapt`. `plan_pruning` returns `{prunable, exempt}` consumed verbatim in `duplicates.py`. `match_items(items, criteria)` signature matches between `rules.py`, tests, and `collections.autobuild`. Function names (`choose_keeper`, `rank_versions`, `resolution_rank`, `plan_pruning`, `match_items`) are used consistently. ✓

**Note for executor:** Live Plex operations (Tasks 5,6,8,9,10 manual steps) require the user's server and can't be auto-verified; treat the import checks + unit tests as the automated gate and surface the manual steps to the user.
