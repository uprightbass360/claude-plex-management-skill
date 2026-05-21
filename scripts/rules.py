"""Pure matching for auto-building collections. No plexapi imports."""


def match_items(items, criteria):
    """Return items matching criteria, using OR semantics across filter kinds.

    An item is included if EITHER condition holds:
      - its title is in criteria["titles"], OR
      - it matches ALL field_filters (every non-"titles" key equals the item's
        value for that field).

    criteria keys:
      - "titles": list of exact titles to include (match any one)
      - any other key: exact-match against that field on the item (all required)

    So {"titles": ["A"], "director": "Nolan"} matches items titled "A" OR
    directed by Nolan — not the intersection. Empty criteria matches nothing
    (avoids accidental whole-library grouping).
    """
    if not criteria:
        return []
    titles = set(criteria.get("titles", []))
    field_filters = {k: v for k, v in criteria.items() if k != "titles"}

    out = []
    for item in items:
        if titles and item.get("title") in titles:
            out.append(item)
            continue
        if field_filters and all(
            item.get(k) == v for k, v in field_filters.items()
        ):
            out.append(item)
    return out


def _contains_tag(item, key, value):
    """True if item[key] (a list of tag strings) contains value, case-insensitive."""
    tags = [str(t).lower() for t in (item.get(key) or [])]
    return str(value).lower() in tags


def match_smart(items, criteria):
    """Return items matching ALL given criteria (AND semantics). Empty -> [].

    Supported criteria keys:
      - genre/director/actor: item's list field (genres/directors/actors) contains
        the value (case-insensitive).
      - decade: int like 1980 -> item year in [1980, 1989].
      - year_from / year_to: inclusive year bounds.
      - rating: a str or list of strs -> item['rating'] must be one of them.
    A criterion whose data is missing on an item fails that item.
    """
    if not criteria:
        return []

    list_field = {"genre": "genres", "director": "directors", "actor": "actors"}
    out = []
    for item in items:
        ok = True
        for key, value in criteria.items():
            if key in list_field:
                if not _contains_tag(item, list_field[key], value):
                    ok = False; break
            elif key == "decade":
                y = item.get("year")
                if y is None or not (value <= y < value + 10):
                    ok = False; break
            elif key == "year_from":
                y = item.get("year")
                if y is None or y < value:
                    ok = False; break
            elif key == "year_to":
                y = item.get("year")
                if y is None or y > value:
                    ok = False; break
            elif key == "rating":
                allowed = value if isinstance(value, (list, tuple, set)) else [value]
                if item.get("rating") not in allowed:
                    ok = False; break
            else:
                ok = False; break  # unknown criterion -> no match (fail safe)
        if ok:
            out.append(item)
    return out


def criteria_to_plex_filters(criteria):
    """Map friendly criteria to a Plex smart-collection filter dict.

    Single clause -> plain dict; multiple -> {"and":[...]}. A multi-value rating
    becomes an {"or":[...]} over contentRating. Raises ValueError if empty.
    Note: Plex's own filter matching (esp. genre) is broader than our exact
    metadata logic, so dynamic collections may include more than the static
    equivalent.
    """
    clauses = []
    if "genre" in criteria: clauses.append({"genre": criteria["genre"]})
    if "director" in criteria: clauses.append({"director": criteria["director"]})
    if "actor" in criteria: clauses.append({"actor": criteria["actor"]})
    if "decade" in criteria: clauses.append({"decade": criteria["decade"]})
    if "year_from" in criteria: clauses.append({"year>>": criteria["year_from"]})
    if "year_to" in criteria: clauses.append({"year<<": criteria["year_to"]})
    if "rating" in criteria:
        rating = criteria["rating"]
        if isinstance(rating, (list, tuple, set)):
            rlist = list(rating)
            if len(rlist) == 1:
                clauses.append({"contentRating": rlist[0]})
            else:
                clauses.append({"or": [{"contentRating": r} for r in rlist]})
        else:
            clauses.append({"contentRating": rating})
    if not clauses:
        raise ValueError("at least one filter required")
    if len(clauses) == 1:
        return clauses[0]
    return {"and": clauses}


def resolve_targets(where):
    """Map a 'home'|'recommended'|'both' choice to the tuple of targets to act on."""
    if where == "both":
        return ("home", "recommended")
    if where in ("home", "recommended"):
        return (where,)
    raise ValueError(f"invalid target {where!r}; use home, recommended, or both")
