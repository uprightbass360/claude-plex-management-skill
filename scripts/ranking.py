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
