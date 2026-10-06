# Hui Jun (June) Wen — Portfolio

Static site (HTML/CSS/JS, no build step). Open `index.html`, or deploy the folder to GitHub Pages / Netlify / Vercel.

## Images

Files in `assets/`. A missing file shows a labeled placeholder.

| File | Status |
|---|---|
| `flyer_1.jpg` … `flyer_7.jpg` | ✅ Seminar flyers (rendered from the original PDFs) |
| `event_1.jpg`, `event_2.jpg` | ✅ Fallback community photos, shown until the gallery is built |
| `digital_*.jpg` | ✅ WeChat Video / WeChat articles / RedNote screenshots |
| `headshot.jpg` | ✅ Headshot |
| `rebrand/*-before.jpg`, `rebrand/*-after.jpg` | ✅ 5 featured before/after signage pairs (32 available — run `tools.build_rebrand` below to see or change them; it writes `tools/out/rebrand-pairs.json`, which is gitignored and only exists after you run it) |
| `events/`, `events/thumbs/` | Generated — curated event photos and thumbnails |
| `Hui_Jun_Wen_Resume.pdf` | ✅ Final résumé |

## Pages

| Page | Contents |
|---|---|
| `index.html` | One-page portfolio, 4 case studies, featured event strip |
| `events.html` | Filterable event gallery, rendered from `data/events.js` |

`data/events.js` assigns `window.GALLERY_DATA` and is loaded with a plain
`<script>` tag, not `fetch()`, so both pages work opened directly as `file://`.

The Partnership section on `index.html` (`[data-featured]`) shows the two
original photos until `data/events.js` has at least one photo marked
`"featured": true` — it is never worse than it looks today. Once real
featured photos exist, `script.js` replaces them with up to 8 photos in a
grid, and "See all events →" links to the full gallery.

## Tooling

Everything in `tools/` is read-only with respect to the OneDrive archive. It
needs no dependencies: Python 3.9 standard library plus macOS `sips`.

```bash
# 0. Publish (or change) the featured before/after signage pairs on index.html.
#    Matches every address that appears on both sides of the rebrand, then
#    downloads and publishes only the chosen ones -- a couple files per pair,
#    not the whole archive. Omit --only for the first 5 matches, or list
#    slugs in the order you want them to appear (see the printed snippet's
#    `data-label` for each slug, or read tools/out/rebrand-pairs.json after
#    running this once).
python3 -m tools.build_rebrand \
  --archive "$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos" \
  --only 2251-86th-st 94-bowery 1865-86th-st SLUG SLUG
#    -> assets/rebrand/*.jpg, tools/out/rebrand-pairs.json, and a snippet to
#       paste into index.html's [data-ba] block. LOOK at every image before
#       publishing it -- nothing automated checks for faces or third-party
#       contact details in these photos either.

# 1. Audit the archive. Downloads nothing.
python3 -m tools.manifests --archive "$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos"
#    -> tools/out/{inventory,duplicates,rename-plan}.csv, events-manifest.md,
#       cleanup.sh, undo.sh

# 2. Tick the events you want in tools/out/events-manifest.md, then download them.
python3 -m tools.hydrate --archive "$ARCHIVE" --manifest tools/out/events-manifest.md

# 3. Build thumbnails and the picker, then open it and choose photos.
python3 -m tools.thumbs --archive "$ARCHIVE" --manifest tools/out/events-manifest.md
open tools/picker/index.html        # export selection.json when done

# 4. Publish the chosen photos.
python3 -m tools.build_assets --archive "$ARCHIVE" --selection ~/Downloads/selection.json

# 5. Check before pushing.
python3 -m tools.verify
```

`tools/out/cleanup.sh` moves duplicate files into a dated quarantine folder
inside the archive. It defaults to a dry run, never deletes, and ships with
`undo.sh`. Review it, then run `bash tools/out/cleanup.sh --apply` yourself.

### The numbers

- The archive has **142 unique events total: 133 have photos, and 9 are
  empty event folders** (no photos were ever filed in them). 133 + 9 = 142
  — the empty folders are part of that total, not an addition to it. Both
  lists are in `tools/out/events-manifest.md`.
- Separately, **1 month folder is empty** (`2026 Event/October Event`) — it
  holds no events at all, so it is not one of the 142 and is reported on
  its own in `events-manifest.md`.
- `cleanup.sh` can safely move **2,548 files (7.67 GB)** — duplicates sitting
  in catch-all folders that mirror a sibling event folder exactly. The
  archive's *total* name+size duplication is larger, **2,917 files
  (10.12 GB)**; the extra 369 files/2.45 GB live outside catch-all folders,
  where picking which copy to keep needs a person, so `cleanup.sh` leaves
  them alone. **`cleanup.sh` only reclaims the 7.67 GB figure, never the
  10.12 GB one.**

### A gap to know about

`tools/out/rename-plan.csv` excludes the 28 folders that `cleanup.sh` would
quarantine as verified duplicates — sensible if you run the cleanup, but
`cleanup.sh` is dry-run by default and you may never run it, in which case
those 28 folders have no rename guidance anywhere in the toolchain.

### Needs your decision

Two things only you can resolve; the tooling never guesses either one.

1. **`Centerlight Health Fair` has two dates.** The same 27 files are filed
   under both `2023 Events/11.23.23 Centerlight Health Fair` and
   `2023 Events/231113 Centerlight Health Fair` — is it 2023-11-13 or
   2023-11-23?
2. **The `Other` category can hide staff-facing events.** It's a catch-all
   for folders that don't match any keyword rule, so it can include things
   like `Anthem BCBS Health Care AEEP In Roll` or `UHC 2026 AEP Rollout
   Dinner - Flushing` — internal insurance-enrollment events, not public
   community programs. Check each row in that section of
   `events-manifest.md` before publishing, the same way you would for
   Internal / Provider. `Other` itself is a normal, publishable category —
   it just needs a look first.

## Tests

```bash
python3 -m unittest discover -s tools/tests -t .
node --test tools/tests/js/*.test.js
```
