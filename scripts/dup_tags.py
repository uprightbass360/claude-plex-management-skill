"""Pure heuristics to label duplicate Plex versions. No plexapi imports.

Distinguishes real alternate encodes (MAIN) from things that only LOOK like
duplicates to Plex: sample clips, bonus/extra features, and multi-track discs.
A suggested keeper is only ever chosen among MAIN versions; SAMPLE/EXTRA/
MULTITRACK are never auto-suggested for keeping or removal — the agent/user
decides explicitly.
"""
import re

try:
    from ranking import resolution_rank
except ImportError:  # package-style import (tests run from repo root)
    from scripts.ranking import resolution_rank

_SAMPLE_RE = re.compile(r"(^|[^a-z])sample([^a-z]|$)", re.IGNORECASE)
_EXTRA_RE = re.compile(
    r"/0?\s*extras?/|trailer|commentary|featurette|deleted.scenes|"
    r"interview|behind.the.scenes|bonus", re.IGNORECASE)
_MULTITRACK_RE = re.compile(r"track\s*\d+", re.IGNORECASE)


def classify_version(version):
    """Return a tag for one version dict: SAMPLE | EXTRA | MULTITRACK | MAIN."""
    path = version.get("file") or ""
    if _SAMPLE_RE.search(path):
        return "SAMPLE"
    if _EXTRA_RE.search(path):
        return "EXTRA"
    if _MULTITRACK_RE.search(path):
        return "MULTITRACK"
    return "MAIN"


def tag_group(versions):
    """Return versions (copies) each with 'tag' and 'suggested_keeper' (bool).

    The suggested keeper is the best MAIN by resolution -> bitrate -> size.
    If there is no MAIN version, nothing is suggested (suggested_keeper all False).
    """
    tagged = []
    for v in versions:
        item = dict(v)
        item["tag"] = classify_version(v)
        item["suggested_keeper"] = False
        tagged.append(item)

    mains = [t for t in tagged if t["tag"] == "MAIN"]
    if mains:
        best = max(mains, key=lambda v: (
            resolution_rank(v.get("resolution")),
            v.get("bitrate") or 0,
            v.get("size") or 0,
        ))
        best["suggested_keeper"] = True
    return tagged
