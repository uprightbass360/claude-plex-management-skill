"""Create, edit, and auto-build collections/boxsets."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse

import _client
import rules


def create(server, section_title, name, rating_keys):
    section = server.library.section(section_title)
    items = [server.fetchItem(int(k)) for k in rating_keys]
    _client.audit("create_collection", server=_client.server_name(server), section=section_title, name=name, count=len(items))
    section.createCollection(title=name, items=items)
    print(f"Created collection '{name}' with {len(items)} items.")


def add(server, rating_key, item_keys):
    col = server.fetchItem(int(rating_key))
    items = [server.fetchItem(int(k)) for k in item_keys]
    _client.audit("add_items", server=_client.server_name(server), ratingKey=str(rating_key), count=len(items))
    col.addItems(items)
    print(f"Added {len(items)} items to '{col.title}'.")


def remove(server, rating_key, item_keys):
    col = server.fetchItem(int(rating_key))
    items = [server.fetchItem(int(k)) for k in item_keys]
    _client.audit("remove_items", server=_client.server_name(server), ratingKey=str(rating_key), count=len(items))
    col.removeItems(items)
    print(f"Removed {len(items)} items from '{col.title}'.")


def rename(server, rating_key, new_title):
    col = server.fetchItem(int(rating_key))
    _client.audit("rename_collection", server=_client.server_name(server), ratingKey=str(rating_key), new=new_title)
    col.editTitle(new_title)
    print(f"Renamed collection to '{new_title}'.")


def delete(server, rating_key):
    col = server.fetchItem(int(rating_key))
    title = col.title
    _client.audit("delete_collection", server=_client.server_name(server), ratingKey=str(rating_key), title=title)
    col.delete()
    print(f"Deleted collection '{title}'.")


def label(server, rating_key, labels):
    """Add one or more labels to a collection (native Plex metadata)."""
    col = server.fetchItem(int(rating_key))
    _client.audit("add_label", server=_client.server_name(server),
                  ratingKey=str(rating_key), title=col.title, labels=labels)
    col.addLabel(labels)
    col.reload()  # reflect server state, not the stale in-memory label list
    current = [l.tag for l in col.labels]
    print(f"Labeled '{col.title}' with {labels}. Now: {current}")


def unlabel(server, rating_key, labels):
    """Remove one or more labels from a collection."""
    col = server.fetchItem(int(rating_key))
    _client.audit("remove_label", server=_client.server_name(server),
                  ratingKey=str(rating_key), title=col.title, labels=labels)
    col.removeLabel(labels)
    col.reload()  # reflect server state, not the stale in-memory label list
    current = [l.tag for l in col.labels]
    print(f"Removed {labels} from '{col.title}'. Now: {current}")


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
    _client.audit("create_collection", server=_client.server_name(server), section=section_title, name=name, count=len(plex_items), via="autobuild")
    section.createCollection(title=name, items=plex_items)
    print(f"Created '{name}' with {len(plex_items)} items.")


def smartbuild(server, section_title, name, criteria, dry_run, dynamic=False):
    """Build a collection from genre/decade/year/rating filters (AND semantics).

    Static by default (precise, exact metadata match). With dynamic=True, creates
    a native Plex SMART collection that auto-updates but uses Plex's broader
    filter matching.
    """
    section = server.library.section(section_title)
    if dynamic:
        plex_filters = rules.criteria_to_plex_filters(criteria)
        if "genre" in criteria or len(criteria) > 1:
            print("NOTE: dynamic/smart collections use Plex's filter matching, "
                  "which is broader than the exact static build (esp. genre).")
        if dry_run:
            print(f"(dry-run) Would create SMART collection '{name}' with Plex "
                  f"filters: {plex_filters}\n"
                  "Membership is computed by Plex and can't be previewed without "
                  "creating it (and may be broader than the static build).\n"
                  "Re-run with --apply to create.")
            return
        col = section.createCollection(title=name, smart=True, filters=plex_filters)
        _client.audit("create_collection", server=_client.server_name(server),
                      section=section_title, name=name, count=col.childCount,
                      via="smartbuild-dynamic", criteria=str(criteria),
                      filters=str(plex_filters))
        print(f"Created SMART collection '{name}' ({col.childCount} items, "
              "auto-updates as the library changes).")
        return
    items = _movie_dicts(section)
    matched = rules.match_smart(items, criteria)
    print(f"{len(matched)} items match {criteria}:")
    for m in matched:
        print(f"  [{m['ratingKey']}] {m['title']} ({m['year']})")
    if dry_run:
        print("\n(dry-run) Re-run with --apply to create the collection.")
        return
    if not matched:
        print("No matches; nothing to create.")
        return
    plex_items = [server.fetchItem(int(m["ratingKey"])) for m in matched]
    _client.audit("create_collection", server=_client.server_name(server),
                  section=section_title, name=name, count=len(plex_items),
                  via="smartbuild", criteria=str(criteria))
    section.createCollection(title=name, items=plex_items)
    print(f"Created '{name}' with {len(plex_items)} items.")
    # remember the rule so `resync` can keep this collection up to date
    new_col = section.collection(name)
    _client.record_collection({"name": name, "ratingKey": str(new_col.ratingKey),
                               "section": section_title, "criteria": criteria})


def _movie_dicts(section):
    """All movies in a section as dicts for rules.match_smart (with ratingKey)."""
    out = []
    for i in section.all():
        out.append({
            "ratingKey": str(i.ratingKey), "title": i.title,
            "year": getattr(i, "year", None),
            "genres": [g.tag for g in getattr(i, "genres", [])],
            "directors": [d.tag for d in getattr(i, "directors", [])],
            "actors": [r.tag for r in getattr(i, "roles", [])],
            "rating": getattr(i, "contentRating", None),
        })
    return out


def resync(server, section_title, only_name, dry_run):
    """Add-only: for each manifest collection in this section, add films that
    match its saved criteria but aren't in the collection yet. Never removes."""
    manifest = [e for e in _client.load_manifest()
                if e.get("section") == section_title
                and (only_name is None or e.get("name") == only_name)]
    if not manifest:
        print(f"No manifest entries for section '{section_title}'"
              + (f" named '{only_name}'." if only_name else "."))
        return
    section = server.library.section(section_title)
    movies = _movie_dicts(section)
    for entry in manifest:
        criteria = entry["criteria"]
        matched = {m["ratingKey"] for m in rules.match_smart(movies, criteria)}
        try:
            col = server.fetchItem(int(entry["ratingKey"]))
        except Exception:
            print(f"! '{entry['name']}' (ratingKey {entry['ratingKey']}) not found; skipping.")
            continue
        current = {str(c.ratingKey) for c in col.items()}
        to_add = sorted(matched - current)
        stale = sorted(current - matched)  # reported only, never removed
        print(f"\n{entry['name']}: {len(to_add)} to add, "
              f"{len(stale)} no longer match (kept).")
        for rk in to_add:
            title = next((m["title"] for m in movies if m["ratingKey"] == rk), rk)
            print(f"  + [{rk}] {title}")
        if dry_run or not to_add:
            continue
        _client.audit("resync_add", server=_client.server_name(server),
                      ratingKey=entry["ratingKey"], title=entry["name"],
                      added=to_add, criteria=str(criteria))
        col.addItems([server.fetchItem(int(rk)) for rk in to_add])
        print(f"  -> added {len(to_add)} to '{entry['name']}'.")
    if dry_run:
        print("\n(dry-run) Re-run with --apply to add the '+' items.")


def _apply_promotion(hubobj, targets, promote):
    """Promote or demote a ManagedHub/collection-visibility for the given targets."""
    for t in targets:
        if t == "home":
            (hubobj.promoteHome if promote else hubobj.demoteHome)()
        elif t == "recommended":
            (hubobj.promoteRecommended if promote else hubobj.demoteRecommended)()


def home_status(server, section_title):
    """Read-only: print built-in hubs and promoted collections in display order."""
    section = server.library.section(section_title)
    print("Built-in hubs:")
    for i, h in enumerate(section.managedHubs(), 1):
        home = "HOME" if getattr(h, "promotedToOwnHome", False) else "    "
        rec = "REC" if getattr(h, "promotedToRecommended", False) else "   "
        print(f"  {i:2d}. [{home}|{rec}] {getattr(h,'title',h.identifier)}  ({h.identifier})")
    print("\nPromoted collections:")
    any_promoted = False
    for c in section.collections():
        try:
            v = c.visibility()
        except Exception:
            continue
        if getattr(v, "promotedToOwnHome", False) or getattr(v, "promotedToRecommended", False):
            any_promoted = True
            home = "HOME" if v.promotedToOwnHome else "    "
            rec = "REC" if v.promotedToRecommended else "   "
            print(f"  [{home}|{rec}] {c.title}")
    if not any_promoted:
        print("  (none)")


def home_promote(server, section_title, collection_name, where, promote):
    """Promote/demote a collection to Home/Recommended (where: home|recommended|both)."""
    section = server.library.section(section_title)
    col = section.collection(collection_name)
    targets = rules.resolve_targets(where)
    _client.audit("home_promote" if promote else "home_demote",
                  server=_client.server_name(server), title=collection_name,
                  targets=list(targets))
    _apply_promotion(col.visibility(), targets, promote)
    print(f"{'Promoted' if promote else 'Demoted'} '{collection_name}' "
          f"{'to' if promote else 'from'} {', '.join(targets)}.")


def home_hub(server, section_title, identifier, where, promote):
    """Promote/demote a built-in managed hub by its identifier."""
    section = server.library.section(section_title)
    hubs = {h.identifier: h for h in section.managedHubs()}
    if identifier not in hubs:
        raise SystemExit(f"No hub '{identifier}'. Available: {', '.join(hubs)}")
    targets = rules.resolve_targets(where)
    _client.audit("home_hub_promote" if promote else "home_hub_demote",
                  server=_client.server_name(server), hub=identifier,
                  targets=list(targets))
    _apply_promotion(hubs[identifier], targets, promote)
    print(f"{'Promoted' if promote else 'Demoted'} hub '{identifier}' "
          f"{'to' if promote else 'from'} {', '.join(targets)}.")


def home_move(server, section_title, identifier, after_identifier):
    """Reorder a built-in hub: move it after another hub (or to front if after is None)."""
    section = server.library.section(section_title)
    hubs = {h.identifier: h for h in section.managedHubs()}
    if identifier not in hubs:
        raise SystemExit(f"No hub '{identifier}'. Available: {', '.join(hubs)}")
    after = None
    if after_identifier:
        if after_identifier not in hubs:
            raise SystemExit(f"No hub '{after_identifier}'.")
        after = hubs[after_identifier]
    _client.audit("home_move", server=_client.server_name(server),
                  hub=identifier, after=after_identifier)
    hubs[identifier].move(after=after)
    print(f"Moved hub '{identifier}' "
          + (f"after '{after_identifier}'." if after_identifier else "to front."))


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

    psb = sub.add_parser("smartbuild",
                         help="Build by genre/decade/year/rating filters (AND).")
    psb.add_argument("section"); psb.add_argument("name")
    psb.add_argument("--genre")
    psb.add_argument("--director")
    psb.add_argument("--actor")
    psb.add_argument("--decade", type=int)
    psb.add_argument("--year-from", type=int, dest="year_from")
    psb.add_argument("--year-to", type=int, dest="year_to")
    psb.add_argument("--rating", help="One rating or comma-separated set, e.g. G,PG")
    psb.add_argument("--dynamic", action="store_true",
                     help="Create a native Plex SMART collection that auto-updates "
                          "(uses Plex's broader matching).")
    psb.add_argument("--apply", action="store_true")

    pl = sub.add_parser("label", help="Add label(s) to a collection.")
    pl.add_argument("rating_key"); pl.add_argument("labels", nargs="+")
    pul = sub.add_parser("unlabel", help="Remove label(s) from a collection.")
    pul.add_argument("rating_key"); pul.add_argument("labels", nargs="+")

    prs = sub.add_parser("resync", help="Add newly-matching films to rule-based collections (add-only).")
    prs.add_argument("section")
    prs.add_argument("--name", help="Only resync the collection with this name.")
    prs.add_argument("--apply", action="store_true")

    ph = sub.add_parser("home", help="Manage Home/Recommended panels.")
    hsub = ph.add_subparsers(dest="home_cmd", required=True)
    hsub.add_parser("status").add_argument("section")
    hp = hsub.add_parser("promote"); hp.add_argument("section"); hp.add_argument("name")
    hp.add_argument("--to", choices=["home","recommended","both"], default="both")
    hd = hsub.add_parser("demote"); hd.add_argument("section"); hd.add_argument("name")
    hd.add_argument("--from", dest="where_from", choices=["home","recommended","both"], default="both")
    hh = hsub.add_parser("hub"); hh.add_argument("section"); hh.add_argument("identifier")
    hh.add_argument("--demote", action="store_true", help="Demote instead of promote.")
    hh.add_argument("--to", choices=["home","recommended","both"], default="both")
    hmv = hsub.add_parser("move"); hmv.add_argument("section"); hmv.add_argument("identifier")
    hmv.add_argument("--after", help="Hub identifier to place this one after (omit = front).")

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
    elif args.cmd == "smartbuild":
        criteria = {}
        if args.genre: criteria["genre"] = args.genre
        if args.director: criteria["director"] = args.director
        if args.actor: criteria["actor"] = args.actor
        if args.decade is not None: criteria["decade"] = args.decade
        if args.year_from is not None: criteria["year_from"] = args.year_from
        if args.year_to is not None: criteria["year_to"] = args.year_to
        if args.rating: criteria["rating"] = [r.strip() for r in args.rating.split(",")]
        if not criteria:
            raise SystemExit(
                "smartbuild needs at least one filter "
                "(--genre, --director, --actor, --decade, --year-from, "
                "--year-to, or --rating).")
        smartbuild(server, args.section, args.name, criteria,
                   dry_run=not args.apply, dynamic=args.dynamic)
    elif args.cmd == "label":
        label(server, args.rating_key, args.labels)
    elif args.cmd == "unlabel":
        unlabel(server, args.rating_key, args.labels)
    elif args.cmd == "resync":
        resync(server, args.section, args.name, dry_run=not args.apply)
    elif args.cmd == "home":
        if args.home_cmd == "status":
            home_status(server, args.section)
        elif args.home_cmd == "promote":
            home_promote(server, args.section, args.name, args.to, promote=True)
        elif args.home_cmd == "demote":
            home_promote(server, args.section, args.name, args.where_from, promote=False)
        elif args.home_cmd == "hub":
            home_hub(server, args.section, args.identifier, args.to, promote=not args.demote)
        elif args.home_cmd == "move":
            home_move(server, args.section, args.identifier, args.after)


if __name__ == "__main__":
    main()
