"""Force OneDrive to download selected events.

macOS File Provider materializes a placeholder when its bytes are read, so
reading the file through to the end is the download. This is the only module
that reads bytes in bulk -- everything else works on metadata.
"""
import argparse
import os
import re
import sys

from tools import eventdata, scan

_TICK = re.compile(r"^\|\s*\[(x)\]\s*\|.*`([^`]+)`\s*\|\s*$", re.I)


def is_hydrated(path):
    try:
        return os.stat(path).st_blocks > 0
    except OSError:
        return False


def pull(path, chunk=1024 * 1024):
    try:
        with open(path, "rb") as fh:
            while fh.read(chunk):
                pass
        return True
    except (OSError, IOError):
        return False


def ids_from_manifest(path):
    ids = []
    with open(path) as fh:
        for line in fh:
            match = _TICK.match(line.strip())
            if match:
                ids.append(match.group(2))
    return ids


def run(archive, event_ids, progress=None):
    wanted = set(event_ids)
    events = eventdata.collect_events(list(scan.walk(archive)))
    chosen = [e for e in events if e["id"] in wanted]
    stats = {"events": len(chosen), "files": 0, "already": 0,
             "pulled": 0, "failed": 0, "bytes": 0}
    for event in chosen:
        for row in event["rows"]:
            stats["files"] += 1
            stats["bytes"] += row["bytes"]
            if is_hydrated(row["path"]):
                stats["already"] += 1
            elif pull(row["path"]):
                stats["pulled"] += 1
            else:
                stats["failed"] += 1
            if progress:
                progress(row)
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download selected events only.")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--events", nargs="*", default=[])
    ap.add_argument("--manifest", help="read ticked [x] rows from this manifest")
    args = ap.parse_args(argv)

    ids = list(args.events)
    if args.manifest:
        ids.extend(ids_from_manifest(args.manifest))
    if not ids:
        print("no events selected: pass --events or tick rows in --manifest")
        return 1

    done = [0]
    total = [0]

    def progress(row):
        done[0] += 1
        if done[0] % 25 == 0 or done[0] == total[0]:
            print("  %d files..." % done[0])

    print("downloading %d events" % len(set(ids)))
    stats = run(args.archive, ids, progress=progress)
    print("files    %d (%.1f GB)" % (stats["files"], stats["bytes"] / 1024.0 ** 3))
    print("already  %d" % stats["already"])
    print("pulled   %d" % stats["pulled"])
    if stats["failed"]:
        print("FAILED   %d -- re-run to retry" % stats["failed"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
