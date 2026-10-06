"""Aggregate inventory rows into one record per event.

Shared by the manifests (Phase B) and the picker (Phase C) so both describe
events identically.
"""
import os
import re

from tools import classify, naming


def year_hint(year_folder):
    if not year_folder:
        return None
    match = re.search(r"(20\d{2})", year_folder)
    return int(match.group(1)) if match else None


def _event_dirs(rows):
    """Event folders that hold files, keyed (top, year, event, catchall)."""
    groups = {}
    for row in rows:
        if not row["event"]:
            continue
        key = (row["top"], row["year"], row["event"], row["catchall"])
        groups.setdefault(key, []).append(row)
    return groups


def collect_events(rows, extra_dirs=None, tops=("Event Photos",)):
    """One record per event folder.

    `tops` restricts which top-level folders count. It defaults to the events
    tree only: the signage folders are keyed by borough, so leaving them in
    would list "Chinatown" and "Brooklyn" as events.
    """
    if tops:
        rows = [r for r in rows if r["top"] in tops]
    groups = _event_dirs(rows)
    records = []
    for key in groups:
        top, year, event, catchall = key
        group = groups[key]
        hint = year_hint(year)
        parsed = naming.parse_date(event, hint)
        title = naming.clean_title(event)
        records.append({
            "top": top,
            "year": year,
            "year_num": hint,
            "event": event,
            "title": title,
            "iso": parsed["iso"] if parsed else None,
            "date_pattern": parsed["pattern"] if parsed else None,
            "category": classify.category(title),
            "category_label": classify.LABELS[classify.category(title)],
            "physician": classify.physician(title),
            "partners": classify.partners(title),
            "photos": len(group),
            "bytes": sum(r["bytes"] for r in group),
            "hydrated": sum(1 for r in group if r["hydrated"]),
            "catchall": catchall,
            "proposed": naming.proposed_name(event, hint),
            "rows": sorted(group, key=lambda r: r["name"]),
            "dir": os.path.dirname(group[0]["rel"]),
        })

    for folder_rel, top, year, event in (extra_dirs or []):
        hint = year_hint(year)
        parsed = naming.parse_date(event, hint)
        title = naming.clean_title(event)
        records.append({
            "top": top, "year": year, "year_num": hint, "event": event,
            "title": title,
            "iso": parsed["iso"] if parsed else None,
            "date_pattern": parsed["pattern"] if parsed else None,
            "category": classify.category(title),
            "category_label": classify.LABELS[classify.category(title)],
            "physician": classify.physician(title),
            "partners": classify.partners(title),
            "photos": 0, "bytes": 0, "hydrated": 0, "catchall": False,
            "proposed": naming.proposed_name(event, hint),
            "rows": [], "dir": folder_rel,
        })

    records.sort(key=lambda e: (e["iso"] or "9999", e["title"].lower()))
    used = {}
    for record in records:
        base = "%s-%s" % (record["iso"] or (record["year_num"] or "undated"),
                          naming.slugify(record["title"]) or "event")
        base = naming.slugify(base)
        count = used.get(base, 0) + 1
        used[base] = count
        record["id"] = base if count == 1 else "%s-%d" % (base, count)
    return records


def find_empty_event_dirs(root):
    """Event folders containing no files. collect_events() only sees files, so
    empty folders -- which the archive has several of -- need their own pass.

    Events can sit at any depth under the events tree (2026 is filed by
    month, so some empty folders are two levels deep: "2026 Event/<month>/
    <event>"), so this walks every directory rather than assuming a fixed
    depth; only leaf directories with neither files nor subdirectories count
    as empty.
    """
    found = []
    events_top = os.path.join(root, "Event Photos")
    for dirpath, dirnames, filenames in os.walk(events_top):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        real = [f for f in filenames if not f.startswith(".")]
        if real or dirnames:
            continue
        rel = os.path.relpath(dirpath, root)
        parts = rel.split(os.sep)
        if len(parts) < 3:
            continue
        found.append((rel, parts[0], parts[1], parts[-1]))
    return found
