"""Read-only listing of libraries, collections, items, and version detail."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse

import _client


def _fmt_size(num):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":  # TB is the terminal unit; no step beyond
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
