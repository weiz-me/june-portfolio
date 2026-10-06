"""Publish featured before/after signage pairs into assets/rebrand/.

Only the chosen pairs are read, so this hydrates about 2 files per pair
instead of touching the 45 GB archive.
"""
import argparse
import json
import os
import re
import sys

from tools import addresses, images

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".heic", ".jfif", ".tif", ".tiff")


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return slug.strip("-")


def pick_photo(folder):
    """Largest image in `folder`, by logical size. Largest is the best
    proxy for highest quality here; the archive mixes phone and DSLR shots.

    Some "before" entries in `_Original Legacy Rendr Photo` are loose
    files, not folders -- the address lives in the filename and there is
    no sibling folder to list. If `folder` is itself a file, use it
    directly rather than trying to os.listdir() it.
    """
    if os.path.isfile(folder):
        return folder
    best = None
    best_size = -1
    if not os.path.isdir(folder):
        return None
    for name in sorted(os.listdir(folder)):
        if name.startswith("."):
            continue
        if not name.lower().endswith(IMAGE_EXTS):
            continue
        full = os.path.join(folder, name)
        if not os.path.isfile(full):
            continue
        size = os.path.getsize(full)
        if size > best_size:
            best, best_size = full, size
    return best


def _side(src, assets_dir, assets_rel, slug, side):
    dst_rel = "%s/%s-%s.jpg" % (assets_rel, slug, side)
    dst = os.path.join(assets_dir, "%s-%s.jpg" % (slug, side))
    info = images.web(src, dst)
    return dst_rel, info


def _select(pairs, limit, only):
    """Decide which pairs to attempt publishing, and in what order.

    When `only` is a non-empty list of slugs, it selects exactly those
    pairs, in the order given, and `limit` is ignored. An `only` slug
    that matches no pair is reported back as an unresolved slug so the
    caller can record it in `skipped` rather than silently dropping it.
    When `only` is None or empty, the first `limit` pairs (in the sorted
    order `match_pairs` already returns) are selected -- this is the
    brief's original behavior.

    Returns (selected_pairs, unresolved_slugs).
    """
    if only:
        by_slug = {}
        for pair in pairs:
            by_slug.setdefault(slugify(pair["label"]), pair)
        selected = []
        unresolved = []
        for slug in only:
            pair = by_slug.get(slug)
            if pair is None:
                unresolved.append(slug)
            else:
                selected.append(pair)
        return selected, unresolved
    return pairs[:limit], []


def build(archive, out_dir, assets_dir, limit=5, only=None):
    """Match every pair, publish either the first `limit` of them, or --
    when `only` is a non-empty list of label slugs -- exactly those pairs
    in the order given (see `_select`)."""
    pairs = addresses.match_pairs(archive)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)
    assets_rel = "assets/rebrand"

    selected, unresolved = _select(pairs, limit, only)

    published = []
    skipped = []
    for slug in unresolved:
        skipped.append({
            "slug": slug,
            "label": None,
            "why": "no pair matches slug %r" % slug,
        })
    for pair in selected:
        before_src = pick_photo(pair["before_dir"])
        after_src = pick_photo(pair["after_dir"])
        if not before_src or not after_src:
            skipped.append({
                "slug": slugify(pair["label"]),
                "label": pair["label"],
                "why": "no image on one side",
            })
            continue
        slug = slugify(pair["label"])
        try:
            before_rel, info = _side(before_src, assets_dir, assets_rel, slug, "before")
            after_rel, _ = _side(after_src, assets_dir, assets_rel, slug, "after")
        except images.SipsError as exc:
            skipped.append({"slug": slug, "label": pair["label"], "why": str(exc)})
            continue
        published.append({
            "slug": slug,
            "label": pair["label"],
            "before": before_rel,
            "after": after_rel,
            "w": info["w"],
            "h": info["h"],
        })

    with open(os.path.join(out_dir, "rebrand-pairs.json"), "w") as fh:
        json.dump({"pairs": pairs, "published": published, "skipped": skipped},
                  fh, indent=2)
    return {"pairs": pairs, "published": published, "skipped": skipped}


def html_snippet(published):
    """Markup for the index.html component. Every pair ships as real markup so
    the component works with JavaScript disabled; JS only toggles .active."""
    blocks = []
    for i, p in enumerate(published):
        cls = "ba-pair active" if i == 0 else "ba-pair"
        blocks.append(
            '            <div class="%s" data-ba-pair data-label="%s">\n'
            '              <figure><img src="%s" alt="Signage at %s before the Rendr rebrand" '
            'data-slot="Before: %s" loading="lazy"><figcaption>Before</figcaption></figure>\n'
            '              <figure><img src="%s" alt="Rendr signage at %s after the rebrand" '
            'data-slot="After: %s" loading="lazy"><figcaption>After</figcaption></figure>\n'
            '            </div>'
            % (cls, p["label"], p["before"], p["label"], p["label"],
               p["after"], p["label"], p["label"])
        )
    return "\n".join(blocks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish rebrand before/after pairs.")
    ap.add_argument("--archive", required=True, help="Event_photos root (read-only)")
    ap.add_argument("--limit", type=int, default=5, help="pairs to publish")
    ap.add_argument("--only", nargs="+", default=None,
                     help="publish exactly these label slugs, in this order "
                          "(overrides --limit)")
    ap.add_argument("--out", default="tools/out")
    ap.add_argument("--assets", default="assets/rebrand")
    args = ap.parse_args(argv)

    result = build(args.archive, args.out, args.assets, args.limit, args.only)
    print("matched %d pairs, published %d, skipped %d"
          % (len(result["pairs"]), len(result["published"]), len(result["skipped"])))
    for s in result["skipped"]:
        print("  skipped %s: %s" % (s["label"] or s["slug"], s["why"]))
    print("\n--- paste into index.html ---\n")
    print(html_snippet(result["published"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
