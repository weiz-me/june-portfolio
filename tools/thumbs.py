"""Generate thumbnails and the local picker page.

The picker is local only: it points at absolute archive paths so clicking a
thumbnail opens the full original, which is how faces get checked before
anything is published. It is never committed and never deployed.

Event folders hold more than photos -- .mov/.mp4 clips, .tif/.dng raw files,
.zip bundles -- and sips cannot make a thumbnail from any of those. Rather
than let them reach images.thumb() and surface as SipsError "conversion"
failures, every file is checked against its extension here, at the call
site, before any sips call is attempted. This mirrors the decision made for
images.py itself: extension policy stays visible in each caller (thumbs.py
here, task 13's module next) instead of living in a shared helper.
"""
import argparse
import html
import os
import sys

from tools import classify, eventdata, hydrate, images, scan

# Extensions sips can actually read and turn into a thumbnail. HEIC and
# JFIF are added on top of images.PUBLISHABLE: sips reads and converts both
# fine, and the archive uses them heavily (738 HEIC, 492 JFIF). Everything
# else -- .mov, .mp4, .tif, .dng, .zip, PDFs, etc. -- is skipped before it
# ever reaches images.thumb().
THUMBABLE = tuple(images.PUBLISHABLE) + ("heic", "jfif")


def _thumb_name(event_id, index):
    return "%s-%03d.jpg" % (event_id, index)


def _skip_reason(ext):
    return "not an image: .%s is not a supported photo extension" % ext


def build(archive, event_ids, thumb_dir, html_path):
    wanted = set(event_ids)
    events = eventdata.collect_events(list(scan.walk(archive)))
    # build() is downstream of a human's explicit pick (via --events or a
    # ticked manifest row) and has no business second-guessing which events
    # exist. Earlier this filtered out every event with catchall=True, on
    # the theory that catch-all folders are always duplicate mirrors -- but
    # that conflated "sits in a folder named in scan.CATCHALLS" with "is a
    # verified duplicate" (dupes.analyze() and manifests.py draw that
    # distinction correctly; thumbs.py should not redraw it here). Honor
    # whatever ids are given.
    chosen = [e for e in events if e["id"] in wanted]
    os.makedirs(thumb_dir, exist_ok=True)

    payload = []
    made = 0
    skipped = []
    for event in chosen:
        photos = []
        for i, row in enumerate(event["rows"], start=1):
            ext = row["ext"].lower()
            if ext not in THUMBABLE:
                skipped.append({"rel": row["rel"], "why": _skip_reason(ext)})
                continue

            name = _thumb_name(event["id"], i)
            dst = os.path.join(thumb_dir, name)
            try:
                if not os.path.exists(dst):
                    images.thumb(row["path"], dst)
                made += 1
            except images.SipsError as exc:
                skipped.append({"rel": row["rel"], "why": str(exc)})
                continue
            photos.append({
                "rel": row["rel"],
                "abs": row["path"],
                "thumb": os.path.join(os.path.basename(thumb_dir), name),
                "caption": event["title"],
            })
        payload.append({
            "id": event["id"],
            "iso": event["iso"],
            "title": event["title"],
            "category": event["category"],
            "category_label": event["category_label"],
            "physician": event["physician"],
            "partners": event["partners"],
            "photos": photos,
        })

    with open(html_path, "w") as fh:
        fh.write(render_html(payload))
    return {"events": len(chosen), "thumbs": made, "skipped": skipped}


def render_html(events):
    groups = []
    for event in events:
        internal = event["category"] == "internal"
        meta = " · ".join(
            [x for x in [event["iso"], event["physician"],
                         ", ".join(event["partners"])] if x]
        )
        tiles = "\n".join(
            '      <label class="tile"><input type="checkbox" data-pick="%s|%s">'
            '<img src="%s" alt="" loading="lazy" data-full="%s">'
            '<input class="cap" type="text" placeholder="caption" '
            'data-cap="%s|%s" value="%s"></label>'
            % (html.escape(event["id"]), html.escape(p["rel"]),
               html.escape(p["thumb"]), html.escape(p["abs"]),
               html.escape(event["id"]), html.escape(p["rel"]),
               html.escape(p["caption"]))
            for p in event["photos"]
        )
        head = '<h2>%s <span class="meta">%s · %d photos</span></h2>' % (
            html.escape(event["title"]), html.escape(meta), len(event["photos"]))
        body = '<div class="tiles" data-category="%s">\n%s\n    </div>' % (
            html.escape(event["category"]), tiles)
        if internal:
            groups.append(
                '  <details class="event internal" data-category="internal">\n'
                '    <summary>⚠ Internal / Provider — %s (%d photos, not '
                'recommended for publication)</summary>\n    %s\n  </details>'
                % (html.escape(event["title"]), len(event["photos"]), body))
        else:
            groups.append('  <section class="event" data-category="%s">\n    %s\n    %s\n  </section>'
                          % (html.escape(event["category"]), head, body))

    filters = "".join(
        '<button type="button" class="filter" data-filter="%s">%s</button>' % (cid, classify.LABELS[cid])
        for cid in classify.CATEGORIES
    )
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>June's Photo Picker</title>
<link rel="stylesheet" href="picker.css">
</head>
<body>
<header>
  <h1>June's Photo Picker</h1>
  <p class="count"><span data-count>0</span> selected · suggested cap 80</p>
  <div class="filters">
    <button type="button" class="filter" data-filter="all">All</button>
    %s
  </div>
  <button type="button" class="export" data-export>Export selection.json</button>
  <p class="hint">Click a thumbnail to open the full-size original and check faces.
  Selections save in this browser, so you can pick across several sittings.</p>
</header>
<main>
%s
</main>
<script src="picker.js"></script>
</body>
</html>
""" % (filters, "\n".join(groups))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build thumbnails and the picker.")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--events", nargs="*", default=[])
    ap.add_argument("--manifest")
    ap.add_argument("--picker", default="tools/picker")
    args = ap.parse_args(argv)

    ids = list(args.events)
    if args.manifest:
        ids.extend(hydrate.ids_from_manifest(args.manifest))
    if not ids:
        print("no events selected: pass --events or tick rows in --manifest")
        return 1

    result = build(args.archive, ids,
                   os.path.join(args.picker, "thumbs"),
                   os.path.join(args.picker, "index.html"))
    print("events %d, thumbnails %d, skipped %d"
          % (result["events"], result["thumbs"], len(result["skipped"])))
    for s in result["skipped"]:
        print("  skipped %s: %s" % (s["rel"], s["why"]))
    print("open %s/index.html" % args.picker)
    return 0


if __name__ == "__main__":
    sys.exit(main())
