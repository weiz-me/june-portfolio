"""Turn selection.json into published assets plus data/events.js.

Data ships as JavaScript rather than JSON because fetch() is blocked on
file:// URLs, and the site must work when index.html is opened directly.
A JSON copy can optionally be written to tools/out/events.json for tooling
and review -- but only when the caller asks for it. `json_path` defaults to
None rather than a cwd-relative "tools/out/events.json": a default like that
would make the test suite (which calls build() from wherever the test
runner's cwd happens to be) write into the real repo on every run. The CLI
passes the real path explicitly; tests never do.

Event folders hold more than photos -- .mov/.mp4 clips, .tif/.dng raw files,
.zip bundles -- and a selection.json a human hand-edited, or a stale picker
export, could still name one. Rather than let that reach images.web/
images.thumb and surface as a SipsError, every selected file is checked
against its extension here, at this call site, before any sips call is
attempted. This mirrors the decision made for thumbs.py and for images.py
itself: extension policy stays visible in each caller instead of living in
a shared helper.
"""
import argparse
import json
import os
import sys

from tools import eventdata, images, scan

# Extensions sips can actually read and publish. HEIC and JFIF are added on
# top of images.PUBLISHABLE, same as tools/thumbs.py's THUMBABLE: sips
# reads and converts both fine. Everything else -- .mov, .mp4, .tif, .dng,
# .zip, etc. -- is skipped before it ever reaches images.web/images.thumb.
PUBLISHABLE = tuple(images.PUBLISHABLE) + ("heic", "jfif")


def _skip_reason(ext):
    return "not an image: .%s is not a supported photo extension" % ext


def _rel_posix(*parts):
    return "/".join(parts)


def build(archive, selection_path, assets_dir, data_path, featured=8,
          json_path=None):
    """Publish the photos named in selection_path and write data_path.

    json_path is opt-in: see the module docstring for why it defaults to
    None instead of a cwd-relative path.
    """
    with open(selection_path) as fh:
        selection = json.load(fh)

    events = {e["id"]: e for e in eventdata.collect_events(list(scan.walk(archive)))}
    rows_by_event = {}
    for event in events.values():
        rows_by_event[event["id"]] = {r["rel"]: r for r in event["rows"]}

    picked = {}
    skipped = []
    for item in selection.get("photos", []):
        event = events.get(item.get("event_id"))
        row = rows_by_event.get(item.get("event_id"), {}).get(item.get("rel"))
        if not event or not row:
            skipped.append({"rel": item.get("rel"), "why": "unknown event or photo"})
            continue
        picked.setdefault(event["id"], []).append((item, row))

    thumbs_dir = os.path.join(assets_dir, "thumbs")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)

    out_events = []
    total_photos = 0
    total_bytes = 0
    featured_left = featured

    for event_id in sorted(picked, key=lambda i: (events[i]["iso"] or "9999", i)):
        event = events[event_id]
        photos = []
        for index, (item, row) in enumerate(picked[event_id], start=1):
            ext = row["ext"].lower()
            if ext not in PUBLISHABLE:
                skipped.append({"rel": row["rel"], "why": _skip_reason(ext)})
                continue

            name = "%s-%03d.jpg" % (event_id, index)
            web_path = os.path.join(assets_dir, name)
            thumb_path = os.path.join(thumbs_dir, name)
            try:
                info = images.web(row["path"], web_path)
                images.thumb(row["path"], thumb_path)
            except images.SipsError as exc:
                skipped.append({"rel": row["rel"], "why": str(exc)})
                continue
            is_featured = featured_left > 0
            if is_featured:
                featured_left -= 1
            photos.append({
                "src": _rel_posix("assets", "events", name),
                "thumb": _rel_posix("assets", "events", "thumbs", name),
                "w": info["w"],
                "h": info["h"],
                "caption": item.get("caption") or event["title"],
                "featured": is_featured,
            })
            total_photos += 1
            total_bytes += info["bytes"]
        if not photos:
            continue
        out_events.append({
            "id": event["id"],
            "date": event["iso"],
            "year": str(event["year_num"]) if event["year_num"] else "",
            "title": event["title"],
            "category": event["category"],
            "category_label": event["category_label"],
            "physician": event["physician"] or "",
            "partners": event["partners"],
            "featured": any(p["featured"] for p in photos),
            "photos": photos,
        })

    data = {"events": out_events}
    data_dir = os.path.dirname(data_path)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)
    with open(data_path, "w") as fh:
        fh.write(render_data_js(data))

    if json_path:
        json_dir = os.path.dirname(json_path)
        if json_dir:
            os.makedirs(json_dir, exist_ok=True)
        with open(json_path, "w") as fh:
            json.dump(data, fh, indent=2)

    return {"events": len(out_events), "photos": total_photos,
            "bytes": total_bytes, "skipped": skipped, "data": data}


def render_data_js(data):
    return "window.GALLERY_DATA = %s;\n" % json.dumps(data, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish selected photos.")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--selection", required=True)
    ap.add_argument("--assets", default="assets/events")
    ap.add_argument("--data", default="data/events.js")
    ap.add_argument("--featured", type=int, default=8)
    ap.add_argument("--json", default="tools/out/events.json")
    args = ap.parse_args(argv)

    result = build(args.archive, args.selection, args.assets, args.data,
                   args.featured, json_path=args.json)
    print("events %d, photos %d, %.1f MB"
          % (result["events"], result["photos"], result["bytes"] / 1048576.0))
    for s in result["skipped"]:
        print("  skipped %s: %s" % (s["rel"], s["why"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
