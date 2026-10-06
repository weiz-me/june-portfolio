"""Find the catch-all folders that duplicate real event folders.

Identity is (filename, size) for every file in the folder. That is strong
enough here: the catch-alls were made by copying, so names and sizes match
exactly, and it costs no reads. A hash would require hydrating 45 GB.

Sibling lookup spans the whole archive, because 2025 Events/archive/ holds
2023 events.
"""
import csv
import os

from tools import naming, scan


def file_key(row):
    return (row["name"].lower(), row["bytes"])


def group_events(rows):
    """key (top, year, event, catchall) -> {"rows", "keys", "bytes"}"""
    groups = {}
    for row in rows:
        if not row["event"]:
            continue
        key = (row["top"], row["year"], row["event"], row["catchall"])
        g = groups.setdefault(key, {"rows": [], "keys": set(), "bytes": 0})
        g["rows"].append(row)
        g["keys"].add(file_key(row))
        g["bytes"] += row["bytes"]
    return groups


def analyze(rows):
    groups = group_events(rows)

    # Index non-catchall folders by normalized event name, archive-wide.
    # Restricted to the events tree: catch-alls only ever exist under
    # "Event Photos", so a signage folder (_Original Excelsior Photos,
    # _Completed Installation Photos, _Original Legacy Rendr Photo) can
    # never legitimately be a catch-all's sibling, even if its slug
    # happens to collide.
    originals = {}
    for key, g in groups.items():
        top, year, event, catchall = key
        if catchall or top != scan.EVENTS_TOP:
            continue
        originals.setdefault(naming.slugify(event), []).append((key, g))

    full, partial, unmatched = [], [], []
    removable_files = removable_bytes = 0

    for key in sorted(groups, key=lambda k: tuple("" if p is None else str(p) for p in k)):
        top, year, event, catchall = key
        if not catchall:
            continue
        g = groups[key]
        candidates = originals.get(naming.slugify(event), [])
        if not candidates:
            unmatched.append({"event": event, "year": year, "rows": g["rows"],
                              "why": "no non-catchall folder with this name"})
            continue
        # Prefer the sibling whose file set covers the most of this folder.
        best_key, best = max(
            candidates, key=lambda item: len(g["keys"] & item[1]["keys"])
        )
        shared = g["keys"] & best["keys"]
        entry = {
            "event": event,
            "year": year,
            "rows": g["rows"],
            "keeps": os.path.dirname(best["rows"][0]["rel"]),
            "shared": len(shared),
        }
        if g["keys"] <= best["keys"]:
            full.append(entry)
            removable_files += len(g["rows"])
            removable_bytes += g["bytes"]
        elif shared:
            dup_rows = [r for r in g["rows"] if file_key(r) in shared]
            entry["dup_rows"] = dup_rows
            entry["unique_rows"] = [r for r in g["rows"] if file_key(r) not in shared]
            partial.append(entry)
            removable_files += len(dup_rows)
            removable_bytes += sum(r["bytes"] for r in dup_rows)
        else:
            entry["why"] = "same name, no shared files"
            unmatched.append(entry)

    return {
        "full": full,
        "partial": partial,
        "unmatched": unmatched,
        "removable_files": removable_files,
        "removable_bytes": removable_bytes,
    }


def write_csv(analysis, path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    written = 0
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rel", "verdict", "bytes", "keeps"])
        for entry in analysis["full"]:
            for row in entry["rows"]:
                writer.writerow([row["rel"], "remove", row["bytes"], entry["keeps"]])
                written += 1
        for entry in analysis["partial"]:
            for row in entry["dup_rows"]:
                writer.writerow([row["rel"], "remove", row["bytes"], entry["keeps"]])
                written += 1
            for row in entry["unique_rows"]:
                writer.writerow([row["rel"], "keep-unique", row["bytes"], ""])
                written += 1
        for entry in analysis["unmatched"]:
            for row in entry["rows"]:
                writer.writerow([row["rel"], "keep-unique", row["bytes"], ""])
                written += 1
    return written


def global_redundancy(rows):
    """Archive-wide name+size redundancy, independent of catch-all/sibling
    relationships.

    analyze()'s full/partial/removable_* figures are scoped to catch-all
    folders paired with a sibling event -- that scoping is what makes it
    safe for cleanup.sh to act on automatically. This function instead asks
    a simpler, broader question: across the *entire* archive, how many
    files share an exact (name, size) with another file somewhere else?
    That total is necessarily >= the catch-all-scoped figure, because every
    catch-all duplicate is by construction a (name, size) match too. The
    gap between the two is duplicate files living outside any catch-all,
    where picking which copy to keep is a judgment call for a human, so
    they are reported but never queued for an automatic move.
    """
    groups = {}
    for row in rows:
        groups.setdefault(file_key(row), []).append(row)
    files = 0
    total_bytes = 0
    for (name, size), group in groups.items():
        if len(group) > 1:
            extra = len(group) - 1
            files += extra
            total_bytes += extra * size
    return {"files": files, "bytes": total_bytes}
