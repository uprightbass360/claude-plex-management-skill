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
