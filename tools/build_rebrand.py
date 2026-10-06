"""Publish featured before/after signage pairs into assets/rebrand/.

Only the chosen pairs are read, so this hydrates about 2 files per pair
instead of touching the 45 GB archive.
"""
import argparse
import html
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
    directly rather than trying to os.listdir() it -- but only if it is
    actually an image. The archive has 12 PDFs mixed in among these loose
    files, and `sips` happily reads and converts a PDF (it renders the
    page as a raster image, no error, exit 0) -- confirmed against a real
    malformed-but-recoverable PDF in this environment. Without this
    extension check, a PDF whose filename parses as an address would be
    silently published as a genuine before photo.
    """
    if os.path.isfile(folder):
        if folder.lower().endswith(IMAGE_EXTS):
            return folder
        return None
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
    in the order given (see `_select`).

    `assets_dir` must itself be a repo-relative path (e.g. "assets/rebrand",
    the CLI's own default) -- not an absolute filesystem path. The
    repo-relative value recorded in `published`/the JSON is derived
    directly from it (normalized to forward slashes), never hardcoded, so
    it stays correct for whatever `--assets` the caller actually passes.
    """
    pairs = addresses.match_pairs(archive)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)
    assets_rel = os.path.normpath(assets_dir).replace(os.sep, "/").rstrip("/")

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
        written = []
        try:
            before_rel, info = _side(before_src, assets_dir, assets_rel, slug, "before")
            written.append(os.path.join(assets_dir, "%s-before.jpg" % slug))
            after_rel, _ = _side(after_src, assets_dir, assets_rel, slug, "after")
            written.append(os.path.join(assets_dir, "%s-after.jpg" % slug))
        except images.SipsError as exc:
            # Keep the pair atomic: a failure partway through must not
            # leave an orphan file referenced by nothing. Task 15's
            # asset verifier cross-checks in both directions (every
            # referenced file exists, and every file on disk is
            # referenced), so an orphan here would fail that check much
            # later, far from this cause.
            for path in written:
                try:
                    os.remove(path)
                except OSError:
                    pass
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
    the component works with JavaScript disabled; JS only toggles .active.

    Labels come straight from folder names on disk and are not under our
    control -- the real archive has entries with "&" and "(" ")" (e.g.
    "Dr. Daniel Yeoun & lab - 26-19 Francis Lewis Blvd", "Dr. Henry Chen
    - 757 60th Street (Exterior Window)"). A raw "&" is invalid HTML that
    browsers only forgive by accident, so every label is escaped with
    html.escape(..., quote=True) before being placed in either an
    attribute or element-text position.
    """
    blocks = []
    for i, p in enumerate(published):
        cls = "ba-pair active" if i == 0 else "ba-pair"
        label = html.escape(p["label"], quote=True)
        blocks.append(
            '            <div class="%s" data-ba-pair data-label="%s">\n'
            '              <figure><img src="%s" alt="Signage at %s before the Rendr rebrand" '
            'data-slot="Before: %s" loading="lazy"><figcaption>Before</figcaption></figure>\n'
            '              <figure><img src="%s" alt="Rendr signage at %s after the rebrand" '
            'data-slot="After: %s" loading="lazy"><figcaption>After</figcaption></figure>\n'
            '            </div>'
            % (cls, label, p["before"], label, label,
               p["after"], label, label)
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
