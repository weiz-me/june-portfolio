"""Pre-publish checks.

The defect this project set out to fix was an <img> pointing at a file that
did not exist, so that check runs in both directions: nothing referenced may
be missing, and nothing published may be unreferenced.
"""
import argparse
import json
import os
import re
import sys

MAX_FILE_BYTES = 500 * 1024
MAX_ASSETS_BYTES = 30 * 1024 * 1024
BANNED_EXTS = (".heic", ".heics", ".jfif", ".tif", ".tiff", ".dng",
               ".mov", ".mp4", ".zip", ".ppm")
HTML_FILES = ("index.html", "events.html")
_ASSIGN = re.compile(r"^\s*window\.GALLERY_DATA\s*=\s*(.*);\s*$", re.S)
_IMG_SRC = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)


def load_gallery_data(path):
    with open(path) as fh:
        match = _ASSIGN.match(fh.read())
    if not match:
        raise ValueError("%s is not a window.GALLERY_DATA assignment" % path)
    return json.loads(match.group(1))


def _walk_dir(root, base):
    for dirpath, dirnames, filenames in os.walk(base):
        for name in filenames:
            if name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


def _walk_assets(root):
    """assets/events/ only -- the set of files data/events.js can reference."""
    return _walk_dir(root, os.path.join(root, "assets", "events"))


def _walk_all_assets(root):
    """All of assets/, recursively. Used for checks that must hold
    everywhere under assets/ regardless of whether data/events.js or an
    <img> tag references the file: the size cap and the banned-format
    list. Do NOT use this for the orphan check -- assets/rebrand/*.jpg,
    assets/flyer_*.jpg, headshot.jpg and the résumé PDF are referenced from
    HTML, not from data/events.js, and widening orphan detection to all of
    assets/ would wrongly flag every one of them. The orphan check must
    stay scoped to _walk_assets() (assets/events/ only).
    """
    return _walk_dir(root, os.path.join(root, "assets"))


def check(root):
    results = []

    def add(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    data_path = os.path.join(root, "data", "events.js")
    try:
        data = load_gallery_data(data_path)
        add("data/events.js parses", True)
    except (IOError, OSError, ValueError) as exc:
        add("data/events.js parses", False, str(exc))
        return results

    referenced = set()
    for event in data.get("events", []):
        for photo in event.get("photos", []):
            for key in ("src", "thumb"):
                if photo.get(key):
                    referenced.add(photo[key])

    missing = [rel for rel in sorted(referenced)
               if not os.path.exists(os.path.join(root, rel))]
    add("every referenced file exists", not missing, ", ".join(missing[:5]))

    # Orphan detection stays scoped to assets/events/ -- see _walk_all_assets's
    # docstring for why widening it would be wrong.
    on_disk = dict(_walk_assets(root))
    orphans = sorted(set(on_disk) - referenced)
    add("every asset is referenced", not orphans, ", ".join(orphans[:5]))

    # Size cap and banned formats apply to all of assets/, not just
    # assets/events/: a stray .heic or an oversized file dropped anywhere
    # under assets/ is exactly the kind of mistake this checker exists to
    # catch, regardless of whether anything references it yet.
    all_on_disk = dict(_walk_all_assets(root))

    oversized = ["%s (%d KB)" % (rel, os.path.getsize(full) // 1024)
                 for rel, full in sorted(all_on_disk.items())
                 if os.path.getsize(full) > MAX_FILE_BYTES]
    add("no file over 500 KB", not oversized, ", ".join(oversized[:5]))

    banned = [rel for rel in sorted(all_on_disk) if rel.lower().endswith(BANNED_EXTS)]
    add("no web-hostile formats in assets", not banned, ", ".join(banned[:5]))

    assets_root = os.path.join(root, "assets")
    total = 0
    for dirpath, dirnames, filenames in os.walk(assets_root):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    add("assets/ under 30 MB", total <= MAX_ASSETS_BYTES,
        "%.1f MB" % (total / 1048576.0))

    dead = []
    for name in HTML_FILES:
        path = os.path.join(root, name)
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            html = fh.read()
        for src in _IMG_SRC.findall(html):
            if src.startswith(("http://", "https://", "data:", "//")):
                continue
            if not os.path.exists(os.path.join(root, src)):
                dead.append("%s -> %s" % (name, src))
    add("no dead img src in html", not dead, ", ".join(dead[:5]))

    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pre-publish checks.")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    results = check(args.root)
    failed = 0
    for r in results:
        mark = "ok  " if r["ok"] else "FAIL"
        print("%s  %s%s" % (mark, r["check"], (" — " + r["detail"]) if r["detail"] else ""))
        if not r["ok"]:
            failed += 1
    print("\n%d checks, %d failed" % (len(results), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
