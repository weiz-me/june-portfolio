# Event Photo Archive → Portfolio Gallery

**Date:** 2026-10-05
**Status:** Approved, ready for implementation planning

## 1. Goal

Two deliverables from one source archive:

1. **Organize** the Rendr event photo archive on OneDrive — it has 8 competing date formats,
   23 duplicate folders and 10.1 GB of redundant copies.
2. **Publish** a curated subset in `june-portfolio` as a filterable event gallery, and fix the
   two broken images the site already has.

## 2. Source data (measured 2026-10-05)

Root: `~/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos/`

| Metric | Value |
|---|---|
| Files | 9,073 |
| Logical size | 45.4 GB (avg 5.1 MB) |
| Typical original | Canon EOS 6D, 5472×3648 |
| **Downloaded locally** | **0.0%** — all cloud placeholders (`st_blocks == 0`) |
| Redundant copies | 2,917 files = **10.12 GB** global; **7.67 GB** of it inside catch-all folders and safely scriptable |
| Unique events | **132** (122 with photos + 10 empty folders) |
| Duplicate event folders | 23 |

Top-level layout:

| Folder | Files | Role |
|---|---|---|
| `Event Photos/` | 8,155 | Events, by year (2022–2026) |
| `_Completed Installation Photos/` | 340 | Post-rebrand signage, 75 addresses → **rebrand AFTER** |
| `_Original Excelsior Photos/` | 522 | Pre-rebrand signage, by borough → **rebrand BEFORE** |
| `_Original Legacy Rendr Photo/` | 56 | Pre-rebrand legacy Rendr signage → **rebrand BEFORE** |

Per year, after collapsing duplicate folders:

| Year | Unique events | Duplicate folders | Unique photos |
|---|---|---|---|
| 2022 | 9 | 9 | 1,160 |
| 2023 | 16 | 10 | 1,377 |
| 2024 | 18 | 4 | 421 |
| 2025 | 25 | 0 | 1,397 |
| 2026 | 79 | 0 | 1,371 |

File types: 7,520 jpg · 738 heic · 492 jfif · 256 png · 40 jpeg · 12 pdf · 4 tif · 4 mov · 3 zip · 2 mp4 · 2 dng.
HEIC and JFIF (1,230 files) are poorly supported in browsers and must be converted.

### 2.1 How the duplication happened

Each year grew a nested catch-all folder whose children are byte-identical twins of its siblings
(verified by matching filename **and** size across every file):

| Catch-all | Duplicates |
|---|---|
| `2022 Events/2022/` | All 9 of 2022's events — 100% match |
| `2023 Events/2023/` | All 10 of its events — 100% match |
| `2025 Events/archive/` | 5 events that actually belong to **2023** (misfiled) |
| `2024 Events/2024 Events1/`, `2025 Events/2025 Events1/` | Partly duplicate, partly unique — needs per-folder comparison |

`Centerlight Health Fair` is stored **three times** (`2023 Events/11.23.23 …`,
`2023 Events/231113 …`, `2023 Events/2023/231113 …`) — the same 27 HEIC files under two
contradictory dates.

### 2.2 The rebrand before/after match

[`index.html:157-158`](../../../index.html#L157-L158) references `assets/rebrand_before.jpg` and
`assets/rebrand_after.jpg`. **Neither file exists** — Case Study 02 currently renders two broken
images. `README.md` already flags both as `⬜`.

Matching `_Original *` folders against `_Completed Installation Photos/` by normalized street
address yields **32 locations with a complete before/after pair** (44 before keys vs 53 after keys).
Examples:

| Address | Before | After |
|---|---|---|
| 2251 86th St | George Hall, MD | Dr. Hall |
| 94 Bowery | Imaging | Multispecialty |
| 142-18 38th Ave | Zhengbo Huang, MD | Dr. Zhengbo Huang |
| 4211 Kissena Blvd | Legacy Rendr | Dr. Wendy Chung, Suite 1C |

This is direct visual evidence for the site's existing **88% brand-awareness** claim.

## 3. Decisions

| Question | Decision |
|---|---|
| Modify the shared OneDrive? | **No. Read-only.** Produce manifests plus a `cleanup.sh` June reviews and runs herself. |
| Privacy filter for publishing? | **None applied by the tooling.** June judges every photo via a local picker that shows everything. |
| Site structure? | **Featured strip on `index.html` + separate `events.html` gallery** with year/theme filters and a lightbox. |
| Sequencing | **Case 02 before/after ships first** — independent of the archive work, needs ~60 photos, fixes the site's only broken images. |
| Internal/provider events | Shown in the picker but **collapsed and unchecked by default**. Not hidden. |

## 4. Non-goals

- Not downloading the full 45 GB. Ever.
- Not deleting anything from OneDrive — `cleanup.sh` *moves* duplicates and is run by June, not by tooling.
- Not renaming OneDrive folders. The rename plan is advisory output only.
- No build step, framework or bundler. The site stays plain HTML/CSS/JS.
- Not publishing an archive. The gallery is curated evidence (~80 photos), not 5,726.

## 5. Architecture — three-stage funnel

The binding constraint: 45 GB is cloud-only, but June wants to see everything before choosing.
Resolved by narrowing in three stages, so bytes are only fetched for what survives each stage.

```
OneDrive (read-only, 45 GB, cloud)
        │
Stage 1 │ read-only scan — 0 bytes downloaded
        │ metadata is already synced; photo bodies are not touched
        ▼ 4 manifests + cleanup.sh
Stage 2 │ event-level pick → targeted hydration
        │ 132 events → June picks ~25 → ~800 photos ≈ 4 GB → 480px thumbnails
        ▼
Stage 3 │ photo-level pick in a local picker
        │ ~800 thumbnails → June picks ~80
        ▼
assets/events/ + data/events.json → index.html strip + events.html
```

## 6. Stage 1 — read-only scan

`tools/scan.py` walks the tree using `os.stat` only. It never opens a file body, so it triggers no
downloads. Outputs (all under `tools/out/`, git-ignored):

| Output | Contents |
|---|---|
| `inventory.csv` | One row per file: path, event, year, bytes, format, hydrated (`st_blocks > 0`) |
| `duplicates.csv` | The 2,866 redundant copies, each marked keep / remove, with reclaimable bytes |
| `rename-plan.csv` | 132 events: current name → proposed name |
| `events-manifest.md` | 132 events with photo count, inferred category, physician, partners — **this is the Stage 2 picking sheet** |
| `cleanup.sh` + `undo.sh` | Generated, **never executed by tooling** |

Duplicate identity = same basename **and** same size, confirmed across the whole folder, matching
the verification already run for 2022, 2023 and `archive/`. `2024 Events1/` and `2025 Events1/`
contain unique material too, so they are compared per folder and partial overlaps are reported
rather than assumed.

### 6.1 cleanup.sh safety

- Uses `mv` into `Event_photos/_DUPLICATES_2026-10-05/`, preserving relative paths. No `rm`.
- Ships with `undo.sh` that reverses every move.
- Reversible twice over: the move itself, then OneDrive's 93-day recycle bin once June deletes.
- Prints a dry-run summary and requires an explicit confirmation flag to act.

### 6.2 Naming convention

2026's existing pattern is already closest to correct; upgrade it to ISO dates so lexical sort
equals chronological sort.

Format: `YYYY-MM-DD Event Name — Venue/Partner`

```
0512 Blood Pressure Seminar Flushing   →  2022-05-12 Blood Pressure Seminar — Flushing
06102023 CAS Award Gala                →  2023-06-10 CAS Award Gala
11.23.23 Centerlight Health Fair       →  2023-11-13 Centerlight Health Fair
3.29 Dr. David Zhuang Health Talk      →  2025-03-29 Dr. David Zhuang Health Talk
April Event/4.15.2026 - CPC Health Talk →  2026-04-15 CPC Health Talk
```

Year folders are kept (`2022 Events/` → `2022/`). 2026's month layer is dropped — the date is in
the folder name, so the month directory is redundant.

### 6.3 Data ambiguities the scan must surface

These are reported for June to decide, never guessed:

1. **`Centerlight Health Fair` date** — `11.23.23` (Nov 23) vs `231113` (Nov 13) on the same 27 files.
2. **Year-less 2025 folders** — `3.29 Dr. David Zhuang Health Talk` and
   `12.12 Dr. Xian Cheung ACAP Health Seminar on Diabetes` sit under `2025 Events/` with no year.
3. **Empty folders — 10 of them, not 3.** Seven are April/September 2026 events whose folders
   were created and named but never filled: the three `HCS Q2 Birthday Party` locations
   (Bensonhurst, W 7 St, Sheepshead Bay), `UCA Q2 Birthday Celebration`,
   `Serica - The Power of Us AAPI Trailblazers Gala`, `HCS 29th Anniversary Benefit Gala`
   and `9.18 - HCS Health Fair`. The others are `3.29 Dr. David Zhuang Health Talk`,
   `UCA (Cultural)  Event` and `2026 Event/October Event`. Either the photos were never
   filed or they live somewhere else — only June can say which.
4. **Partial-overlap catch-alls** — every file in `2024 Events1/` and `2025 Events1/` that is *not*
   a duplicate is listed explicitly, so nothing unique is swept into `_DUPLICATES_`.

## 7. Stage 2 — event taxonomy and targeted hydration

132 events are classified into 8 categories that map onto claims the site already makes:

| Category | Supports | Examples |
|---|---|---|
| Health Seminars | Case 01 — 46 seminars | Dr. Xian Cheung (diabetes), Dr. Harry He (liver), Deborah Liang (mental health) |
| Community Health Fairs | Partnership section | VNS Health Fair, CCPH Wellness Day, Spring Into Health |
| Grand Openings | Clinic Launches card | Bay St, Flushing STEB, Queens Supersite, UCA Bensonhurst |
| Payer Partnerships | "23 payer & community partners" | UHC, VNS, HCS, Fidelis, WellCare, Centerlight, Anthem |
| Cultural & Parades | Community engagement | Chinatown LNY Parade, Asian Heritage, UCA Mother & Father's Day |
| Sponsorships & Walks | Brand visibility | Breast Cancer Walk, Swim Across America, UHC Golf Outing |
| Galas & Awards | Industry relationships | CAS Award Gala, HCS 26th Anniversary, ACAP Gala, Rendr LNY Gala |
| Internal / Provider | **Not recommended for publication** | Rendr Dinner (642), Provider Holiday Party (488), Team Building (119) |

The internal category holds the largest folders (1,249 photos) and the least recruiter value, and
is entirely colleagues' faces. Per the decision in §3 it appears in the picker, collapsed and
unchecked.

Average unique photos per event is 39 overall, or **31** excluding the three large internal
events, so a ~25-event pick means roughly 800 photos ≈ 4 GB — under 9% of the archive.

`tools/hydrate.py` takes the chosen event list and forces download only for those folders, by
reading each file's bytes to `/dev/null` so the macOS File Provider materializes it. It reports
progress and total bytes, and skips files already hydrated.

## 8. Stage 3 — local photo picker

`tools/picker/index.html`, generated by `tools/thumbs.py`. Local only — never committed, never deployed.

```
┌──────────────────────────────────────────────────────┐
│ June's Photo Picker            selected 42 / cap 80  │
│ [All][Seminars][Fairs][Openings][Payer][Internal ▾]  │
├──────────────────────────────────────────────────────┤
│ ▾ 2026-06-09  Dr. Xian Cheung Diabetes · WellCare+CPC│
│   ☑▣  ☐▣  ☑▣  ☐▣  ☐▣  ☑▣            (11 photos)   │
│ ▾ 2026-03-01  Chinatown LNY Parade                   │
│   ☑▣  ☑▣  ☐▣  ☐▣                     (4 photos)    │
│ ▸ 2022-10-23  Rendr Dinner  ⚠ internal  (642 photos) │
├──────────────────────────────────────────────────────┤
│                [ Export selection.json ]             │
└──────────────────────────────────────────────────────┘
```

- Click a thumbnail to view the full-size image, so faces can be checked before publishing.
- Per-photo caption field, pre-filled from the folder name, editable.
- Selection persists in `localStorage` — picking can span several sittings.
- Exports `selection.json` for Stage 4.

## 9. Site changes

### 9.1 Case 02 — before/after comparison (ships first)

Replaces the two broken `<img>` tags at [`index.html:157-158`](../../../index.html#L157-L158).
Because 32 matched pairs exist, this becomes a switchable comparison rather than a single pair:

```
Case 02  Brand transformation
┌─────────────────────────────────┐
│  ◀  2251 86th St · Brooklyn  ▶  │
│  ┌──────────┐   ┌──────────┐    │
│  │  BEFORE  │ → │  AFTER   │    │
│  │George Hall│   │  Rendr   │    │
│  └──────────┘   └──────────┘    │
│  ● ○ ○ ○ ○   (5 featured of 32) │
└─────────────────────────────────┘
```

5 pairs are published; the remaining 27 stay available in `data/rebrand-pairs.json` for later.
Keyboard-navigable, and degrades to a static first pair with JavaScript disabled.

### 9.2 index.html featured strip

The Partnership section's 2 photos become an 8-photo grid plus a "See all events →" link to
`events.html`. Existing `event_1.jpg` / `event_2.jpg` are kept if June selects them, replaced otherwise.

### 9.3 events.html

New page: year filter × category filter, lightbox, lazy-loaded thumbnails. Fully data-driven —
no photo is hardcoded in markup. Reuses `style.css` tokens and the existing dark-mode toggle, and
adds `gallery.css` / `gallery.js` for gallery-specific behavior. Navigation gains an "Events" link.

### 9.4 data/events.json

```json
{
  "events": [{
    "id": "2026-06-09-cheung-diabetes",
    "date": "2026-06-09",
    "title": "Diabetes: Focus on Diet",
    "category": "seminar",
    "physician": "Dr. Xian Cheung",
    "partners": ["WellCare", "CPC"],
    "venue": "CPC Nan Shan Senior Center",
    "featured": true,
    "photos": [{
      "src": "assets/events/2026-06-09-cheung-diabetes-1.jpg",
      "thumb": "assets/events/thumbs/2026-06-09-cheung-diabetes-1.jpg",
      "w": 1400, "h": 933,
      "caption": "Dr. Cheung presenting to seniors at CPC Nan Shan"
    }]
  }]
}
```

Adding a future event means editing JSON and dropping in images — no HTML or CSS changes.

## 10. Image pipeline and size budget

Available tooling on this machine: **`sips` only**. No ImageMagick, `convert`, `cwebp`, `exiftool`
or Pillow. `python3` is `/usr/bin/python3`; `node` is in `~/.local/bin`.

`sips` capabilities, verified:

- HEIC → JPEG: **works** (tested on a cloud-only `.HEIC`, which also confirms hydrate-on-read).
- WebP: **readable, not writable.** Output format is therefore **JPEG**.

Measured on a real 5472×3648 Canon original from the archive:

| Setting | Size |
|---|---|
| Original | 5.1 MB |
| 1600px q78 | 389 KB |
| **1400px q68 — chosen** | **267 KB** |
| 1200px q60 | 178 KB |
| Thumbnail 480px q70 | 60 KB |

Budget at ~80 published photos: **≈21 MB full-size + ≈5 MB thumbnails ≈ 26 MB**, well inside
GitHub Pages' 1 GB limit. First paint loads thumbnails only.

`tools/build-assets.py` reads `selection.json`, converts and resizes through `sips`, writes
`assets/events/` plus `assets/events/thumbs/`, and generates `data/events.json` with real
pixel dimensions so the gallery can reserve layout space and avoid shifting.

## 11. Work order

| # | Step | Needs June | Blocked by sync? |
|---|---|---|---|
| 1 | Scan, 4 manifests, `cleanup.sh` | — | No — runs on metadata |
| 2 | **Case 02 before/after (32 pairs)** | pick 5 | Only ~60 photos |
| 3 | Pick events from `events-manifest.md` | **yes** | No |
| 4 | Targeted hydration + thumbnails | — | Yes, for picked events only |
| 5 | Pick photos in the picker | **yes** | Yes |
| 6 | Build `events.html`, featured strip, JSON | — | No — parallel with 4 and 5 |
| 7 | Pre-publish verification | — | — |

Steps 1, 2 and 6 need no synced bytes at all.

## 12. Verification before publishing

- `du -sh assets/` under 30 MB; no single file over 500 KB.
- No `.heic`, `.jfif`, `.tif`, `.dng`, `.mov`, `.zip` reaches `assets/`.
- Every `src` in `data/events.json` resolves to a file on disk, and every file in
  `assets/events/` is referenced by the JSON — checked both directions.
- No `<img>` in `index.html` or `events.html` points at a missing file — the specific defect
  being fixed, so it is explicitly re-tested.
- Renders correctly at 375px width with no horizontal scroll, in light and dark mode.
- Filters and lightbox work; gallery degrades gracefully with JavaScript disabled.
- `README.md` image table updated — `rebrand_*` rows move from `⬜` to `✅`.
- OneDrive is unchanged: `git`-external, but confirmed by re-running the scan and diffing
  `inventory.csv` against the pre-work run.

## 13. Files

**New**

```
tools/scan.py              read-only scan → manifests
tools/hydrate.py           targeted download of picked events
tools/thumbs.py            thumbnails + generates the picker
tools/build-assets.py      selection.json → assets/events/ + data/events.json
tools/picker/index.html    local picker (git-ignored)
tools/out/                 manifests, cleanup.sh (git-ignored)
events.html                public gallery
gallery.css, gallery.js    gallery-only styles and behavior
data/events.json           gallery data
data/rebrand-pairs.json    32 before/after pairs
assets/events/             published photos + thumbs/
```

**Changed**

```
index.html    Case 02 before/after component; Partnership strip; nav "Events" link
style.css     shared tokens used by gallery.css
README.md     image table; tools and workflow documentation
.gitignore    tools/out/, tools/picker/thumbs/
```
