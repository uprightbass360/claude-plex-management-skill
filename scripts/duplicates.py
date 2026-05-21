"""Find duplicate Plex versions (read-only scan) and delete specific versions.

`scan "<Section>"`            human-readable, labeled report (read-only)
`scan "<Section>" --json`     same data as JSON for programmatic/agent use
`delete "<Section>" <id>...`  delete ONLY the named Media version ids (after a
                              printed confirmation). No automatic selection.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import json

import _client
import dup_tags


def _fmt_size(num):
    num = num or 0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":  # TB is the terminal unit; no step beyond
            return f"{num:.1f}{unit}"
        num /= 1024


def _versions(item):
    """Version dicts for one item, each carrying its live Media handle + id."""
    out = []
    for m in item.media:
        size = sum((p.size or 0) for p in m.parts)
        file = next((p.file for p in m.parts if p.file), "")
        out.append({"media_id": m.id, "resolution": m.videoResolution,
                    "bitrate": m.bitrate or 0, "size": size, "file": file,
                    "_media": m})
    return out


def scan_groups(server, section_title):
    """Return tagged duplicate groups for a section (read-only)."""
    section = server.library.section(section_title)
    exempt = _client.load_exempt_keys()
    groups = []
    for item in section.search(duplicate=True):
        if len(item.media) <= 1:
            continue
        tagged = dup_tags.tag_group(_versions(item))
        groups.append({
            "ratingKey": str(item.ratingKey),
            "title": item.title,
            "exempt": str(item.ratingKey) in exempt,
            "versions": tagged,
        })
    return groups


def _public(group):
    """Strip the live _media handle so a group is JSON-serializable."""
    return {**group, "versions": [{k: v for k, v in ver.items() if k != "_media"}
                                  for ver in group["versions"]]}


def print_scan(groups):
    if not groups:
        print("No multi-version items found.")
        return
    for g in groups:
        flag = "  [EXEMPT]" if g["exempt"] else ""
        print(f"\n{g['title']} (ratingKey={g['ratingKey']}){flag}")
        for v in g["versions"]:
            star = "*" if v["suggested_keeper"] else " "
            print(f"  {star}[{v['media_id']}] {v['tag']:<10} "
                  f"{v['resolution']} {v['bitrate']}kbps {_fmt_size(v['size'])}")
            print(f"        {v['file']}")
    print("\n* = suggested keeper (best MAIN). Tags: MAIN / SAMPLE / EXTRA / "
          "MULTITRACK.\nNothing is deleted by scan. To remove specific versions:")
    print('  python3 scripts/duplicates.py delete "<Section>" <media_id> ...')


def delete_versions(server, section_title, media_ids):
    """Delete ONLY the given Media ids found in this section's duplicate groups."""
    wanted = set(int(i) for i in media_ids)
    by_id = {}
    for g in scan_groups(server, section_title):
        for v in g["versions"]:
            if v["media_id"] in wanted:
                by_id[v["media_id"]] = (g, v)

    missing = wanted - set(by_id)
    if missing:
        raise SystemExit(
            "These media_ids were not found among duplicates in "
            f"'{section_title}': {sorted(missing)}. Re-run scan to get current ids.")

    print("About to DELETE these versions (Plex moves files to its trash):")
    for mid in sorted(by_id):
        g, v = by_id[mid]
        print(f"  [{mid}] {g['title']} — {v['tag']} {v['resolution']} "
              f"{_fmt_size(v['size'])}\n        {v['file']}")

    srv = _client.server_name(server)
    deleted = 0
    for mid in sorted(by_id):
        g, v = by_id[mid]
        _client.audit("delete_version", server=srv, ratingKey=g["ratingKey"],
                      title=g["title"], media_id=mid, file=v["file"],
                      size=v["size"], resolution=v["resolution"], tag=v["tag"])
        v["_media"].delete()
        deleted += 1
    print(f"\nDeleted {deleted} version(s). (Plex trash, not a permanent wipe.)")


def main():
    _client.ensure_venv()
    p = argparse.ArgumentParser(description="Scan for duplicate versions / delete specific ones.")
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scan", help="Read-only: list multi-version items.")
    ps.add_argument("section")
    ps.add_argument("--json", action="store_true", help="Emit JSON.")
    pd = sub.add_parser("delete", help="Delete ONLY the named Media version ids.")
    pd.add_argument("section")
    pd.add_argument("media_ids", nargs="+", type=int)

    args = p.parse_args()
    server = _client.connect()
    if args.cmd == "scan":
        groups = scan_groups(server, args.section)
        if args.json:
            print(json.dumps([_public(g) for g in groups], indent=2))
        else:
            print_scan(groups)
    elif args.cmd == "delete":
        delete_versions(server, args.section, args.media_ids)


if __name__ == "__main__":
    main()
