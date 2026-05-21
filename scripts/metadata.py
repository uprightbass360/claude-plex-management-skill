"""Edit basic item metadata: title, sort title, poster."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse

import _client


def set_title(server, rating_key, value):
    item = server.fetchItem(int(rating_key))
    old = item.title
    _client.audit("set_title", server=_client.server_name(server), ratingKey=str(rating_key), old=old, new=value)
    item.editTitle(value)
    print(f"Title: '{old}' -> '{value}'")


def set_sort_title(server, rating_key, value):
    item = server.fetchItem(int(rating_key))
    _client.audit("set_sort_title", server=_client.server_name(server), ratingKey=str(rating_key), new=value)
    item.editSortTitle(value)
    print(f"Sort title set to '{value}' for '{item.title}'.")


def set_poster(server, rating_key, url):
    item = server.fetchItem(int(rating_key))
    _client.audit("set_poster", server=_client.server_name(server), ratingKey=str(rating_key), url=url)
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
