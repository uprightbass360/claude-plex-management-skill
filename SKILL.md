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
not authenticated.

**Preferred (non-blocking, agent-friendly) — split flow:** PIN auth blocks while
polling, so don't run the blocking command yourself. Instead:

    python3 scripts/auth.py start          # prints a code + https://plex.tv/link, returns immediately

Relay the code + link to the user; wait for them to authorize in a browser; then:

    python3 scripts/auth.py finish [--server "<name>"]   # claims the token

`finish` discovers the account's servers. If there is more than one, it lists
them and exits asking you to re-run with `--server "<name>"`. A PIN is single-use;
`finish` persists the claimed token so a server-selection retry reuses it. On
success it saves a token (file mode 0600). Never print the token.

**Alternative (interactive/blocking):** `python3 scripts/auth.py` (or
`auth.py interactive`) runs the whole flow in one blocking call — only suitable
when a human runs it directly in a terminal, not when an agent drives it.

## Verify the setup (read-only)

Right after authenticating — or whenever something seems off — run the
connectivity self-test. It confirms the token and server are reachable and
changes nothing:

    python3 scripts/selftest.py

It prints the connected server name/version, the Plex account, and the library
list. If it reports "Not authenticated", run `scripts/auth.py`; if the server is
unreachable, the error shows the URL it tried.

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
- Label/unlabel (organize collections by category in Plex): `python3 scripts/manage_collections.py label <collectionKey> <label>...` / `unlabel ...`. Native Plex labels (filter the Collections view by them).
- Keep rule-based collections current (add-only): `python3 scripts/manage_collections.py resync "<Section>" [--name "<Name>"]` — dry-run shows newly-matching films to add per collection; `--apply` adds them. Never removes (stale items only reported). Only covers collections recorded in the manifest (smartbuild records automatically; explicit-list collections like the director boxsets are NOT auto-resynced).
- Home/Recommended panels (all via `python3 scripts/manage_collections.py home <action>`): `home status "<Section>"` (read-only: built-in hubs + promoted collections, in order); `home promote "<Section>" "<Name>" [--to home|recommended|both]` and `home demote ... [--from ...]` to add/remove a collection as a Home shelf; `home hub "<Section>" <identifier> [--to ...] [--demote]` to toggle a built-in suggestion hub; `home move "<Section>" <identifier> [--after <id>]` to reorder. All reversible + audit-logged. Confirm with the user before promoting/reordering.
- Auto-build, single exact field (dry-run): `python3 scripts/manage_collections.py autobuild "<Section>" "<Name>" <field> "<value>"` — add `--apply` to create. Note: `field` is an exact-equality scalar match; for genre/director (tag-lists) use smartbuild instead.
- Smart-build by metadata filters (dry-run): `python3 scripts/manage_collections.py smartbuild "<Section>" "<Name>" [--genre G] [--director D] [--actor A] [--decade 1980] [--year-from Y --year-to Y] [--rating G,PG]` — AND semantics across filters; tag-list fields matched case-insensitively; add `--apply` to create. Examples: `--genre Horror --decade 1980`, `--genre Family --rating G,PG`, `--actor "Bruce Campbell"`. At least one filter is required. Builds a STATIC collection (exact, recorded in the manifest for `resync`).
  - Add `--dynamic` to instead create a NATIVE Plex SMART collection that auto-updates server-side (no resync needed). Caveat: Plex's filter matching is BROADER than the static build (esp. genre — e.g. a smart genre=Horror pulls in some sci-fi). Dynamic dry-run only shows the Plex filter, not membership (Plex computes that). Dynamic collections are NOT recorded in the manifest. Use static for precision, dynamic for zero-maintenance.

Always dry-run first (omit `--apply`) and show the user the matched list before creating. Echo what will change before applying. For delete and bulk operations, confirm
with the user first.

## Metadata

- `python3 scripts/metadata.py title <ratingKey> "<New Title>"`
- `python3 scripts/metadata.py sort-title <ratingKey> "<Sort Title>"`
- `python3 scripts/metadata.py poster <ratingKey> "<image-url>"`

These are live edits — state the exact change and confirm with the user before
running.

## Duplicates: scan (read-only) → user picks → delete by id (DESTRUCTIVE)

The tool does NOT auto-choose what to delete. It finds multi-version items and
labels each version; the user decides; you delete only the exact ids they pick.

1. Scan (read-only — deletes nothing). For reasoning, use `--json`:

       python3 scripts/duplicates.py scan "<Section>" --json

   Each version has a stable `media_id` and a `tag`:
   - `MAIN` — a real alternate encode of the film.
   - `SAMPLE` — a short sample clip. NEVER delete the real movie in favor of a
     sample; a sample often has a higher bitrate but tiny size.
   - `EXTRA` — bonus feature/commentary/trailer (path under Extras). These are
     NOT redundant copies; don't delete unless the user explicitly wants to.
   - `MULTITRACK` — a track of a multi-part disc, not a duplicate.
   `suggested_keeper` marks the best MAIN, but it is ADVISORY only. Groups the
   user exempted show `"exempt": true`.

2. Summarize for the user and let them choose which `media_id`s to remove. Watch
   for traps: if the proposed removal is much LARGER than the keeper, or tagged
   SAMPLE/EXTRA/MULTITRACK, flag it rather than deleting.

3. ONLY delete the specific ids the user approved:

       python3 scripts/duplicates.py delete "<Section>" <media_id> <media_id> ...

   It prints a confirmation list, aborts atomically if any id is unknown, audits
   each deletion, and removes ONLY those versions. State that Plex routes deleted
   files to its trash, not a hard wipe. Never delete a version the user didn't
   explicitly name.

To keep a whole group untouched, add its ratingKey to
`~/.config/plex-collection-manager/exemptions.json` (a `ratingKeys` list) or via
`_client.add_exempt_key()`.

## Audit log (every write is recorded)

Every server-modifying action — version deletes, collection create/edit/delete,
metadata edits — appends one JSON line to
`~/.config/plex-collection-manager/audit.log` *before* the change is made
(timestamp, action, server, ratingKey/title, and details like file+size or
old→new). It is append-only; read-only actions write nothing. Review it with:

    python3 scripts/audit.py            # full log
    python3 scripts/audit.py --tail 20  # last 20 entries

After a delete batch, point the user here to see exactly what was removed (Plex
keeps deleted files in its trash, so the log tells them what to restore).

## Notes

- The first script run creates `.venv/` and installs plexapi; this is expected.
- If a script reports "Not authenticated", run `scripts/auth.py`.
- If the server is unreachable, the error shows the URL tried; the token may have
  expired — re-run auth.
