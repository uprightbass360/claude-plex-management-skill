# Plex Collection Manager — a Claude skill

A [Claude Code](https://claude.com/claude-code) skill for operating a Plex Media
Server conversationally: authenticate, browse libraries, organize
collections/boxsets, edit metadata, prune duplicate media, and curate the
Home/Recommended screen — all with a hard safety rail around anything
destructive.

You talk to Claude in plain language ("find duplicate movies in Movies",
"build an 80s horror collection", "put Studio Ghibli on the home screen") and
Claude runs the right operation against your server.

## What it can do

- **Authenticate** via Plex's official PIN OAuth flow (a non-blocking
  `start`/`finish` flow plus an interactive one); the token is stored outside the
  repo, `chmod 600`.
- **Browse** (read-only): libraries, collections, items, and per-version detail
  (resolution, bitrate, file size, path).
- **Organize collections / boxsets**: create, rename, delete, add/remove items;
  rule-based building by genre / decade / year / actor / director / rating
  (`smartbuild`) as either precise **static** collections or native
  **auto-updating Plex smart collections** (`--dynamic`); categorize collections
  with native Plex **labels**; keep static rule-based collections current as your
  library grows (`resync`, add-only).
- **Edit metadata**: title, sort title, poster.
- **Prune duplicates safely**: a read-only scan labels each version
  `MAIN`/`SAMPLE`/`EXTRA`/`MULTITRACK`; you pick exactly which versions to
  delete by id — the tool never auto-deletes.
- **Curate the Home screen**: promote/demote collections and built-in suggestion
  hubs to Home/Recommended, and reorder them.
- **Audit log**: every server-modifying action is appended to a local JSONL log
  *before* it happens, so you always have a record of what changed.

## Safety model

- **Read-only by default.** `selftest`, `browse`, and `duplicates scan` change
  nothing.
- **Deletes only what you name.** `duplicates delete` removes only the exact
  version ids you approve, aborts atomically if any id is unknown, and Plex
  routes deleted files to its trash (not a hard wipe).
- **Everything is reversible or recorded.** Labels and Home promotions are
  reversible; every write is in the audit log (`scripts/audit.py`).
- **Secrets stay out of the repo.** Token, exemptions, pending-login, audit log,
  and the collection manifest all live in `~/.config/plex-collection-manager/`.

## Install as a Claude Code skill

Clone the repo and symlink (or copy) it into your personal skills directory:

```bash
git clone https://github.com/uprightbass360/claude-plex-management-skill.git
ln -s "$(pwd)/claude-plex-management-skill" ~/.claude/skills/plex-collection-manager
```

Claude discovers the skill via `SKILL.md`. The first run bootstraps an isolated
Python virtualenv and installs [python-plexapi](https://github.com/pkkid/python-plexapi)
automatically.

### Requirements

- Python 3.10+ (developed on 3.12)
- A reachable Plex Media Server and a Plex account
- No system-wide pip needed — the skill creates its own `.venv/`

## First run

```bash
python3 scripts/auth.py start            # prints a code + https://plex.tv/link
# authorize in a browser, then:
python3 scripts/auth.py finish           # add --server "<name>" if you have several
python3 scripts/selftest.py              # confirm connectivity (read-only)
```

## Command reference (summary)

| Area | Command |
|------|---------|
| Auth | `auth.py start` / `auth.py finish [--server NAME]` / `auth.py` (interactive) |
| Verify | `selftest.py` |
| Browse | `browse.py sections \| collections "<Section>" \| items "<Section>" \| item <rk>` |
| Collections | `manage_collections.py create\|add\|remove\|rename\|delete` |
| Build by rule | `manage_collections.py smartbuild "<Section>" "<Name>" [--genre/--director/--actor/--decade/--year-from/--year-to/--rating] [--apply] [--dynamic]` (static, or `--dynamic` for an auto-updating Plex smart collection) |
| Labels | `manage_collections.py label\|unlabel <rk> <label>...` |
| Keep current | `manage_collections.py resync "<Section>" [--name N] [--apply]` |
| Home screen | `manage_collections.py home status\|promote\|demote\|hub\|move ...` |
| Metadata | `metadata.py title\|sort-title\|poster <rk> "<value>"` |
| Duplicates | `duplicates.py scan "<Section>" [--json]` then `duplicates.py delete "<Section>" <media_id>...` |
| Audit | `audit.py [--tail N]` |

See [`SKILL.md`](SKILL.md) for the full operating instructions Claude follows.

## Development

```bash
python3 scripts/_client.py     # bootstrap the venv
.venv/bin/python -m pytest -q  # run the unit tests (pure logic; no live server needed)
```

Pure logic (ranking, tagging, rule-matching, target resolution) is unit-tested;
live Plex operations are exercised manually against a server.

## License

MIT
