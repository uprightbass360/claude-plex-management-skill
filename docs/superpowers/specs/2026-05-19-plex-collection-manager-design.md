# Plex Collection Manager — Skill Design

**Date:** 2026-05-19
**Status:** Approved for planning
**Form factor:** Conversational Claude skill backed by Python scripts

## Purpose

A Claude skill that connects to a Plex Media Server, authenticates via Plex's
official PIN-based OAuth flow, and lets the user organize media, collections,
and boxsets and prune duplicate content through natural-language conversation.
The user talks to Claude in plain language ("find duplicate movies", "build a
boxset for this series", "keep both copies of X"); Claude selects and runs the
appropriate script against the user's Plex server.

## Goals

- Authenticate to Plex once via PIN OAuth and reuse a long-lived token.
- Browse and inspect libraries, collections, and items (read-only).
- Create and edit collections/boxsets, including auto-building from rules.
- Edit basic metadata and artwork.
- Find duplicate **versions** of the same title and prune them safely.
- Let the user mark certain duplicates as intentional ("keep both") so they are
  never proposed for deletion.

## Non-Goals (YAGNI)

- No standalone CLI distribution or cron automation (conversational use only).
- No username/password or raw-token auth paths (PIN OAuth only).
- No cross-server sync, no Plex Pass-only features beyond what plexapi exposes
  generically, no transcoding/playback management.
- No fuzzy "same title/year" duplicate matching in v1 — only Plex's own
  multi-version groupings.

## Tech Stack

- **Python 3.12** (present at `/usr/bin/python3`).
- **python-plexapi** (`plexapi`) for auth (`MyPlexPinLogin`), library/collection
  management, and media metadata.
- Isolated **venv** at `<skill>/.venv` — system pip is externally managed on this
  machine (PEP 668), so a venv is required. First run bootstraps it.
- Standard library only beyond plexapi (json, pathlib, argparse).

## Directory Layout

```
plex-collection-manager/
├── SKILL.md                  # when-to-use + workflow instructions for Claude
├── scripts/
│   ├── _client.py            # shared: bootstrap venv, load config/token, connect, helpers
│   ├── auth.py               # PIN-based OAuth login → stores token + server choice
│   ├── browse.py             # list libraries / collections / items + version details
│   ├── collections.py        # create/rename/delete/add/remove/order; auto-build by rule
│   ├── metadata.py           # edit titles / sort titles / posters / artwork
│   └── duplicates.py         # find dup versions; dry-run report; --confirm to delete
├── requirements.txt          # plexapi pinned
├── tests/                    # unit tests for pure logic (mocked plexapi)
└── .gitignore                # never commit token/config/venv
```

## Configuration & Secrets

- Config file: `~/.config/plex-collection-manager/config.json`, created `chmod 600`.
  Contents: `{ token, client_id, server_name, server_baseurl }`.
- `client_id` is a persisted random UUID used as `X-Plex-Client-Identifier`.
- Exemptions file: `~/.config/plex-collection-manager/exemptions.json` —
  `{ "ratingKeys": [...], "rules": [...] }`. Items here are reported as
  "duplicate — kept intentionally" and excluded from any delete set.
- `.gitignore` excludes `.venv/`, any local config, and `__pycache__`.
- The token and config are NEVER written into the repo or printed in full.

## Authentication Flow (`auth.py`)

Implements the official PIN flow from
https://developer.plex.tv/pms/#section/API-Info/Authenticating-with-Plex:

1. Generate/persist `X-Plex-Client-Identifier` (UUID) and send required headers
   (`X-Plex-Product`, `X-Plex-Version`, `X-Plex-Device`, `X-Plex-Platform`).
2. Use `MyPlexPinLogin` to request a PIN; print the `https://plex.tv/link` URL
   and code (and/or the direct OAuth URL) for the user to open and approve.
3. Poll until authorized; receive the long-lived auth token.
4. Discover the user's servers via the account resources. If more than one,
   Claude asks the user which to use.
5. Persist `{ token, client_id, server_name, server_baseurl }` to config (0600).

`_client.py` reuses the stored token on every later run. On missing/expired
token or unreachable server, it raises a clear, actionable error telling the
user to re-run auth.

## Browse & Inspect (`browse.py`) — read-only

- List libraries (name, type, item count).
- List collections within a library.
- List items in a library or collection.
- Show item detail: each version's resolution, bitrate, file size, codec, path.
- Output is human-readable tables suitable for Claude to summarize.

## Collections / Organize (`collections.py`)

- Create / rename / delete collections.
- Add / remove items.
- Set sort title and collection order; toggle smart vs. manual where supported.
- **Auto-build by rule:** generate a collection/boxset from criteria — a film
  series into a boxset, by director / genre / year, or from an explicit list of
  titles or ratingKeys the user provides.
- All write operations echo the intended change first. Bulk or destructive
  operations require explicit confirmation before executing.

## Metadata / Artwork (`metadata.py`)

- Edit titles, sort titles, summaries.
- Set posters/artwork (by URL or by selecting from available agents' options).
- Same confirm-before-write discipline as collections.

## Duplicate Detection & Pruning (`duplicates.py`)

- **Scope (v1):** Plex's own multi-version items — one title with multiple
  files/versions (`Video.media` length > 1, via library `duplicates()`).
- **Keeper ranking:** resolution → bitrate → file size (descending). The top
  entry is the proposed keeper; the remainder are removal candidates.
- **Exemptions ("keep both"):** items in `exemptions.json` (by ratingKey or rule)
  are reported as intentionally kept and excluded from the delete set entirely.
  The user can add exemptions conversationally ("keep both copies of X"), and
  Claude may proactively ask when a group looks deliberate (e.g. director's cut
  vs. theatrical).
- **Safety model:**
  - **Dry-run by default.** Prints a table per duplicate group: title, each
    version with size/resolution, the proposed keeper, and what would be removed.
  - Deletion happens ONLY when invoked with an explicit `--confirm` flag, which
    Claude passes only after the user approves a specific batch in conversation.
  - Each delete prompt states that Plex routes deleted files to the OS/Plex
    trash rather than performing a hard wipe.

## Error Handling

- Not authenticated → message instructing the user to run `auth.py`.
- Server unreachable → show the base URL that was tried.
- Ambiguous title → list candidate matches with ratingKeys for disambiguation.
- Any mutation supports a preview/`--dry-run`; `duplicates.py` defaults to it.

## Testing Strategy

- **TDD for pure logic:** keeper-ranking, exemption filtering, and rule matching
  are pure functions unit-tested with mocked plexapi objects — no live server.
- **Connectivity self-test:** a `--self-test` mode confirms auth + server reach
  without mutating anything.
- Tests live in `tests/` and run inside the bootstrapped venv.

## Open Questions

None outstanding. Fuzzy title/year duplicate matching and configurable keeper
rules are explicitly deferred to a future iteration.
