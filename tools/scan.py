"""Read-only inventory of the archive.

Uses os.walk and os.stat only. It never opens a file body, so it triggers
no OneDrive downloads: a cloud-only placeholder reports its real logical size
in st_size while st_blocks stays 0.
"""
import argparse
import csv
import os
import sys

EVENTS_TOP = "Event Photos"

# Per-year folders that mirror their own siblings.
CATCHALLS = ("2022", "2023", "2024 Events1", "2025 Events1", "archive")

# 2026 is filed by month, with the real event one level deeper.
MONTH_LAYER_YEAR = "2026 Event"

INVENTORY_FIELDS = ("rel", "top", "year", "event", "catchall", "name", "ext",
                    "bytes", "hydrated")


def classify_path(rel):
    """Split a relative path into top / year / event, collapsing the 2026
    month layer and recognizing catch-all folders."""
    parts = rel.split(os.sep) if os.sep in rel else rel.split("/")
    out = {"top": parts[0] if parts else None, "year": None,
           "event": None, "catchall": False}
    if out["top"] != EVENTS_TOP:
        if len(parts) >= 2:
            # Signage folders: the deepest directory is the location.
            out["event"] = parts[-2] if len(parts) > 2 else parts[1]
        return out
    if len(parts) < 3:
        return out
    out["year"] = parts[1]
    rest = parts[2:-1] if len(parts) > 3 else parts[2:2]
    if not rest:
        return out
    if out["year"] == MONTH_LAYER_YEAR:
        out["event"] = rest[1] if len(rest) > 1 else rest[0]
    elif rest[0] in CATCHALLS:
        out["catchall"] = True
        out["event"] = rest[1] if len(rest) > 1 else rest[0]
    else:
        out["event"] = rest[0]
    return out


def walk(root):
    """Yield a dict per non-dotfile. Reads metadata only."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            rel = os.path.relpath(path, root)
            info = classify_path(rel)
            _, ext = os.path.splitext(name)
            yield {
                "rel": rel,
                "path": path,
                "top": info["top"],
                "year": info["year"],
                "event": info["event"],
                "catchall": info["catchall"],
                "name": name,
                "ext": ext.lstrip(".").lower(),
                "bytes": st.st_size,
                "hydrated": st.st_blocks > 0,
            }


def write_inventory(root, csv_path):
    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    stats = {"files": 0, "bytes": 0, "hydrated": 0, "hydrated_bytes": 0, "events": 0}
    events = set()
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=INVENTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in walk(root):
            writer.writerow(row)
            stats["files"] += 1
            stats["bytes"] += row["bytes"]
            if row["hydrated"]:
                stats["hydrated"] += 1
                stats["hydrated_bytes"] += row["bytes"]
            if row["event"]:
                events.add((row["top"], row["year"], row["event"]))
    stats["events"] = len(events)
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only archive inventory.")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", default="tools/out")
    args = ap.parse_args(argv)
    stats = write_inventory(args.archive, os.path.join(args.out, "inventory.csv"))
    gb = 1024.0 ** 3
    print("files    %d" % stats["files"])
    print("size     %.1f GB" % (stats["bytes"] / gb))
    print("local    %d files (%.1f GB), %.1f%% downloaded"
          % (stats["hydrated"], stats["hydrated_bytes"] / gb,
             100.0 * stats["hydrated"] / max(stats["files"], 1)))
    print("events   %d" % stats["events"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
