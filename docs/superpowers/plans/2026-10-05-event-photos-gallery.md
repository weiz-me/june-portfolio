# Event Photo Archive → Portfolio Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Organize a 45 GB / 9,073-file Rendr event photo archive without modifying it, and publish a curated, filterable event gallery plus a 32-pair rebrand before/after comparison in `june-portfolio`.

**Architecture:** A read-only Python toolchain under `tools/` narrows the archive in three stages (metadata scan → event pick → photo pick), then emits web-sized JPEGs and a generated JS data file. The site stays a no-build-step static site: a new `events.html` renders entirely from `window.GALLERY_DATA`, and `index.html` gains a switchable before/after component and a featured strip.

**Tech Stack:** Python 3.9.6 stdlib only · macOS `sips` for all image work · vanilla HTML/CSS/JS (no framework, no bundler) · `unittest` and `node --test` for tests.

**Spec:** [`docs/superpowers/specs/2026-10-05-event-photos-gallery-design.md`](../specs/2026-10-05-event-photos-gallery-design.md)

## Global Constraints

Every task's requirements implicitly include this section.

**Environment**
- Python is **3.9.6** (`/usr/bin/python3`). No `match` statements, no `X | Y` annotations, no `dict | dict` merge. Use `typing.Optional`, `typing.List`, `typing.Dict`.
- **Standard library only.** No `pip install`. Pillow, ImageMagick, `convert`, `cwebp` and `exiftool` are all absent.
- Node is v22.23.1 at `~/.local/bin/node`. Shell tool calls that use it must prefix `export PATH="$HOME/.local/bin:$PATH"`.
- Python tests: `python3 -m unittest discover -s tools/tests -t .`
- JS tests: `node --test tools/tests/js/`

**OneDrive is read-only. Absolutely.**
- Archive root: `~/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos/`
- No task may create, rename, move or delete anything under that path. `tools/` opens files for reading only.
- **No test may touch the real archive.** Tests run against synthetic fixtures built by `tools/tests/fixtures.py`.
- `cleanup.sh` is *generated output*, never executed by any task or test.

**Images**
- `sips` can read HEIC/JFIF but **cannot write WebP**. All output is **JPEG**.
- Web size: **1400px long edge, quality 68** (≈267 KB measured). Thumbnails: **480px, quality 70** (≈60 KB measured).
- `sips -Z` **upscales** sources smaller than the target (verified on sips-316: 64x48 at `-Z 4000` returns 4000x3000). Always clamp the target to the source's long edge so small images pass through untouched.
- `assets/` total must stay **under 30 MB**, no single file over **500 KB**.
- Reading a file's bytes hydrates it from the cloud. Never read bytes in bulk outside `tools/hydrate.py`.

**Site**
- No build step, no framework, no bundler. The site must work opened as `file://` *and* served over HTTP.
- Because `fetch()` is blocked on `file://`, gallery data ships as **`data/events.js`** assigning `window.GALLERY_DATA`, loaded with a plain `<script>`. This replaces the spec's `data/events.json`; `tools/out/events.json` is still written as a human-readable copy for tooling.
- For the same reason the spec's `data/rebrand-pairs.json` becomes **`tools/out/rebrand-pairs.json`**: the browser never loads it, because all 5 featured pairs ship as real markup in `index.html`. It stays a tooling record of the full 32.
- `script.js` calls `getElementById("year")`, `querySelector(".theme-toggle")`, `.nav-toggle` and `.nav-links` **with no null checks**. Every page that loads `script.js` must contain all four, or the script throws and the theme toggle plus mobile menu die.
- Reuse `style.css` custom properties. Dark mode is declared twice, as the existing file does: under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` and again under `:root[data-theme="dark"]`.
- Must render at 375px width with no horizontal scroll.
- Missing images degrade via the existing `img[data-slot]` placeholder mechanism in `script.js`.

**Git**
- Work on branch `event-gallery`. Commit at the end of every task.
- End every commit message with:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`

---

## File Structure

**Phase A — rebrand before/after (ships first, independent of the archive)**

| File | Responsibility |
|---|---|
| `tools/tests/fixtures.py` | Builds a synthetic archive in a temp dir: duplicate catch-alls, all 8 date formats, empty folders, real HEIC/JFIF/JPEG bytes |
| `tools/images.py` | The only module that shells out to `sips`. Dimensions, convert-and-resize. |
| `tools/addresses.py` | Street-address normalization and before/after pair matching |
| `tools/build_rebrand.py` | CLI: match pairs, hydrate + convert the featured ones, write `tools/out/rebrand-pairs.json` |
| `assets/rebrand/` | Published before/after JPEGs |

**Phase B — archive organization (read-only)**

| File | Responsibility |
|---|---|
| `tools/naming.py` | Date parsing across 8 formats, conflict detection, slugs, proposed names |
| `tools/scan.py` | Walk + `os.stat` only → `inventory.csv` |
| `tools/dupes.py` | Duplicate grouping, keep/remove decisions, partial-overlap reporting |
| `tools/classify.py` | 8-category classification, physician and partner extraction |
| `tools/manifests.py` | `events-manifest.md`, `rename-plan.csv`, `cleanup.sh`, `undo.sh` |

**Phase C — curation → gallery**

| File | Responsibility |
|---|---|
| `tools/hydrate.py` | Targeted download of picked events only |
| `tools/thumbs.py` | Thumbnails + generates the local picker |
| `tools/build_assets.py` | `selection.json` → `assets/events/` + `data/events.js` |
| `tools/verify.py` | Pre-publish checks (size budget, dead links, banned formats) |
| `events.html`, `gallery.css`, `gallery.js` | The public gallery |

**Modified:** `index.html`, `style.css`, `README.md`, `.gitignore`

---

## Task 1: Test harness and synthetic archive fixtures

Nothing else can be tested safely until there is a fake archive to test against. The real one is 45 GB, cloud-only, and read-only.

**Files:**
- Create: `tools/__init__.py`, `tools/tests/__init__.py`
- Create: `tools/tests/fixtures.py`
- Create: `tools/tests/test_fixtures.py`
- Create: `.gitignore` additions

**Interfaces:**
- Consumes: nothing
- Produces:
  - `fixtures.make_seed_image(path: str, kind: str) -> str` — writes a real image file; `kind` is `"jpg"`, `"heic"` or `"jfif"`. Returns `path`.
  - `fixtures.build_archive(root: str) -> dict` — creates the synthetic archive under `root`; returns a dict with keys `"events"` (int), `"files"` (int), `"dup_files"` (int), `"dup_bytes"` (int).
  - `fixtures.ArchiveFixture` — `unittest.TestCase` mixin exposing `self.archive_root` and cleaning up in `tearDown`.

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_fixtures.py
import os
import unittest

from tools.tests import fixtures


class TestSeedImage(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_makes_a_real_readable_jpeg(self):
        p = fixtures.make_seed_image(os.path.join(self.tmp, "a.jpg"), "jpg")
        self.assertTrue(os.path.exists(p))
        self.assertGreater(os.path.getsize(p), 500)
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(2), b"\xff\xd8")  # JPEG SOI marker

    def test_makes_a_real_heic(self):
        p = fixtures.make_seed_image(os.path.join(self.tmp, "a.heic"), "heic")
        with open(p, "rb") as fh:
            self.assertIn(b"ftyp", fh.read(32))


class TestBuildArchive(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()
        self.stats = fixtures.build_archive(self.tmp)

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_has_the_four_top_level_folders(self):
        for name in ("Event Photos", "_Completed Installation Photos",
                     "_Original Excelsior Photos", "_Original Legacy Rendr Photo"):
            self.assertTrue(os.path.isdir(os.path.join(self.tmp, name)), name)

    def test_duplicate_catchall_mirrors_its_siblings(self):
        sib = os.path.join(self.tmp, "Event Photos", "2022 Events",
                           "0512 Blood Pressure Seminar Flushing")
        nest = os.path.join(self.tmp, "Event Photos", "2022 Events", "2022",
                            "0512 Blood Pressure Seminar Flushing")
        self.assertEqual(sorted(os.listdir(sib)), sorted(os.listdir(nest)))

    def test_reports_duplicate_counts(self):
        self.assertGreater(self.stats["dup_files"], 0)
        self.assertGreater(self.stats["dup_bytes"], 0)

    def test_includes_an_empty_event_folder(self):
        empty = os.path.join(self.tmp, "Event Photos", "2025 Events",
                             "3.29 Dr. David Zhuang Health Talk")
        self.assertTrue(os.path.isdir(empty))
        self.assertEqual(os.listdir(empty), [])
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd /Users/weizhang/Desktop/repos/june-portfolio && python3 -m unittest tools.tests.test_fixtures -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Implement the fixture builder**

Create empty `tools/__init__.py` and `tools/tests/__init__.py`, then:

```python
# tools/tests/fixtures.py
"""Synthetic archive for tests. Never touches the real OneDrive tree."""
import os
import shutil
import struct
import subprocess
import tempfile

# Event folders reproducing every naming pattern found in the real archive.
# (year folder, event folder, number of photos, extension)
EVENTS = [
    ("2022 Events", "0512 Blood Pressure Seminar Flushing", 2, "jpg"),
    ("2022 Events", "1023 Rendr Dinner", 3, "jpg"),
    ("2022 Events", "0817 Team Building Event", 2, "jpg"),
    ("2023 Events", "06102023 CAS Award Gala", 2, "jpg"),
    ("2023 Events", "11.23.23 Centerlight Health Fair", 2, "heic"),
    ("2023 Events", "231113 Centerlight Health Fair", 2, "heic"),
    ("2023 Events", "Provider Holiday Party 12-16-2023", 2, "jpg"),
    ("2024 Events", "09.13.24 PCP End-of-Summer provider dinner", 2, "jpg"),
    ("2024 Events", "Lunar New Year 2024", 1, "jpg"),
    ("2025 Events", "5.8.25 Rendr Flushing STEB Grand Opening", 2, "jpg"),
    ("2025 Events", "12.12 Dr. Xian Cheung ACAP Heath Seminar on Diabetes", 1, "jfif"),
    ("2025 Events", "UHC Golf Outing 5 .7", 1, "jpg"),
]

# Catch-all folders that duplicate their siblings exactly.
CATCHALLS = [
    ("2022 Events", "2022", ["0512 Blood Pressure Seminar Flushing",
                             "1023 Rendr Dinner",
                             "0817 Team Building Event"]),
    ("2023 Events", "2023", ["06102023 CAS Award Gala",
                             "231113 Centerlight Health Fair"]),
]

EMPTY_DIRS = [
    ("2025 Events", "3.29 Dr. David Zhuang Health Talk"),
    ("2025 Events", "UCA (Cultural)  Event"),
    ("2026 Event", "October Event"),
]

# Addresses present on both sides of the rebrand, plus one only-before and
# one only-after, so matching can be tested for misses as well as hits.
BEFORE_DIRS = [
    ("_Original Excelsior Photos", "Brooklyn", "George Hall, MD - 2251 86th St"),
    ("_Original Excelsior Photos", "Manhattan", "Imaging - 94 Bowery"),
    ("_Original Excelsior Photos", "Queens", "Zhengbo Huang, MD - 142-18 38th Ave"),
    ("_Original Excelsior Photos", "Brooklyn", "Nobody - 1 Nowhere St"),
]
AFTER_DIRS = [
    "Dr. Hall - 2251 86th St",
    "Multispecialty - 94 Bowery",
    "Dr. Zhengbo Huang - 142-18 38th Ave",
    "Dr. Unmatched - 999 Elsewhere Ave",
]
LEGACY_FILES = [
    ("Chinatown", "Dr. Jianwei Zhang - 139 Centre St 709 - Entrance Door Logo"),
    ("_Brooklyn", "7217 18th Ave - Logo"),
]


def make_tempdir():
    return tempfile.mkdtemp(prefix="june-fixture-")


def cleanup(path):
    shutil.rmtree(path, ignore_errors=True)


def _write_ppm(path, w=64, h=48, shade=120):
    """A valid binary PPM, which sips can read and convert."""
    with open(path, "wb") as fh:
        fh.write(("P6\n%d %d\n255\n" % (w, h)).encode("ascii"))
        row = bytes([shade, (shade + 60) % 256, (shade + 120) % 256]) * w
        fh.write(row * h)


def make_seed_image(path, kind):
    """Write a real image of the requested kind. Returns path."""
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "jfif": "jpeg", "heic": "heic"}[kind]
    ppm = path + ".ppm"
    _write_ppm(ppm, shade=(abs(hash(os.path.basename(path))) % 200))
    subprocess.check_call(
        ["sips", "-s", "format", fmt, ppm, "--out", path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    os.remove(ppm)
    return path


def _fill(folder, count, ext):
    os.makedirs(folder, exist_ok=True)
    made = []
    for i in range(1, count + 1):
        made.append(make_seed_image(os.path.join(folder, "IMG_%04d.%s" % (i, ext)), ext))
    return made


def build_archive(root):
    """Create the synthetic archive. Returns summary counts."""
    ep = os.path.join(root, "Event Photos")
    files = 0
    for year, event, count, ext in EVENTS:
        files += len(_fill(os.path.join(ep, year, event), count, ext))

    # Catch-alls are byte-identical copies, which is what makes them detectable.
    dup_files = 0
    dup_bytes = 0
    for year, catchall, mirrored in CATCHALLS:
        for event in mirrored:
            src = os.path.join(ep, year, event)
            dst = os.path.join(ep, year, catchall, event)
            shutil.copytree(src, dst)
            for name in os.listdir(dst):
                dup_files += 1
                dup_bytes += os.path.getsize(os.path.join(dst, name))
    files += dup_files

    for year, event in EMPTY_DIRS:
        os.makedirs(os.path.join(ep, year, event), exist_ok=True)

    for top, borough, name in BEFORE_DIRS:
        files += len(_fill(os.path.join(root, top, borough, name), 1, "jpg"))
    for name in AFTER_DIRS:
        files += len(_fill(os.path.join(root, "_Completed Installation Photos", name),
                           1, "jfif"))
    legacy = os.path.join(root, "_Original Legacy Rendr Photo")
    for borough, name in LEGACY_FILES:
        os.makedirs(os.path.join(legacy, borough), exist_ok=True)
        make_seed_image(os.path.join(legacy, borough, name + ".heic"), "heic")
        files += 1

    return {
        "events": len(EVENTS),
        "files": files,
        "dup_files": dup_files,
        "dup_bytes": dup_bytes,
    }


class ArchiveFixture(object):
    """Mixin: gives a TestCase self.archive_root backed by a synthetic tree."""

    def setUp(self):
        self.archive_root = make_tempdir()
        self.archive_stats = build_archive(self.archive_root)

    def tearDown(self):
        cleanup(self.archive_root)
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_fixtures -v`
Expected: PASS, 6 tests. If the HEIC assertion fails, run `sips --formats | grep heic` to confirm `public.heic Writable`.

- [ ] **Step 5: Add .gitignore entries and commit**

Append to `.gitignore`:

```
tools/out/
tools/picker/thumbs/
tools/picker/index.html
__pycache__/
*.pyc
```

```bash
git add tools/__init__.py tools/tests/__init__.py tools/tests/fixtures.py \
        tools/tests/test_fixtures.py .gitignore
git commit -m "$(printf 'test: add synthetic archive fixtures\n\nTests must never touch the real 45 GB cloud-only OneDrive archive, so\nfixtures.py builds a small tree reproducing its real quirks: duplicate\ncatch-all folders, all 8 date formats, empty event folders, and genuine\nHEIC/JFIF/JPEG bytes generated through sips.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: `tools/images.py` — the only module that touches `sips`

**Files:**
- Create: `tools/images.py`
- Create: `tools/tests/test_images.py`

**Interfaces:**
- Consumes: `fixtures.make_seed_image`, `fixtures.make_tempdir`, `fixtures.cleanup`
- Produces:
  - `images.WEB_MAX_PX = 1400`, `images.WEB_QUALITY = 68`, `images.THUMB_MAX_PX = 480`, `images.THUMB_QUALITY = 70`
  - `images.PUBLISHABLE = ("jpg", "jpeg", "png")` — extensions allowed in `assets/`
  - `images.dimensions(path: str) -> tuple` — returns `(width, height)` as ints
  - `images.to_jpeg(src: str, dst: str, max_px: int, quality: int) -> dict` — writes `dst`, returns `{"w": int, "h": int, "bytes": int}`
  - `images.web(src, dst) -> dict` and `images.thumb(src, dst) -> dict` — `to_jpeg` with the constants above
  - `images.SipsError` — raised on any `sips` failure, message includes `sips` stderr

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_images.py
import os
import unittest

from tools import images
from tools.tests import fixtures


class TestImages(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()
        self.jpg = fixtures.make_seed_image(os.path.join(self.tmp, "src.jpg"), "jpg")
        self.heic = fixtures.make_seed_image(os.path.join(self.tmp, "src.heic"), "heic")

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_dimensions_reads_real_pixels(self):
        self.assertEqual(images.dimensions(self.jpg), (64, 48))

    def test_to_jpeg_scales_the_long_edge_and_keeps_aspect(self):
        out = os.path.join(self.tmp, "out.jpg")
        got = images.to_jpeg(self.jpg, out, 32, 70)
        self.assertEqual(got["w"], 32)
        self.assertEqual(got["h"], 24)
        self.assertEqual(images.dimensions(out), (32, 24))
        self.assertEqual(got["bytes"], os.path.getsize(out))

    def test_never_upscales(self):
        # sips -Z on its own WOULD upscale this to 4000x3000; to_jpeg clamps.
        out = os.path.join(self.tmp, "big.jpg")
        got = images.to_jpeg(self.jpg, out, 4000, 70)
        self.assertEqual((got["w"], got["h"]), (64, 48))
        self.assertEqual(images.dimensions(out), (64, 48))

    def test_converts_heic_to_jpeg(self):
        out = os.path.join(self.tmp, "from_heic.jpg")
        images.to_jpeg(self.heic, out, 64, 70)
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(2), b"\xff\xd8")

    def test_creates_missing_parent_directories(self):
        out = os.path.join(self.tmp, "deep", "nested", "out.jpg")
        images.to_jpeg(self.jpg, out, 32, 70)
        self.assertTrue(os.path.exists(out))

    def test_raises_sipserror_with_stderr_on_bad_input(self):
        bad = os.path.join(self.tmp, "not-an-image.jpg")
        with open(bad, "w") as fh:
            fh.write("definitely not a jpeg")
        with self.assertRaises(images.SipsError):
            images.dimensions(bad)

    def test_web_and_thumb_use_the_documented_constants(self):
        self.assertEqual((images.WEB_MAX_PX, images.WEB_QUALITY), (1400, 68))
        self.assertEqual((images.THUMB_MAX_PX, images.THUMB_QUALITY), (480, 70))
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_images -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.images'`

- [ ] **Step 3: Implement it**

```python
# tools/images.py
"""All sips interaction lives here.

sips can read HEIC and JFIF but cannot write WebP, so every output is JPEG.
Sizes and qualities below were measured against a real 5472x3648 Canon
original from the archive: 1400px/q68 lands at ~267 KB, 480px/q70 at ~60 KB.
"""
import os
import subprocess

WEB_MAX_PX = 1400
WEB_QUALITY = 68
THUMB_MAX_PX = 480
THUMB_QUALITY = 70

# Extensions allowed to reach assets/. HEIC, JFIF, TIF, DNG, MOV and ZIP
# all appear in the archive and none of them belong on the web.
PUBLISHABLE = ("jpg", "jpeg", "png")


class SipsError(RuntimeError):
    pass


def _sips(args):
    proc = subprocess.Popen(
        ["sips"] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise SipsError("sips %s failed: %s" % (" ".join(args), err.decode("utf-8", "replace").strip()))
    return out.decode("utf-8", "replace")


def dimensions(path):
    """Return (width, height). Raises SipsError if the file is not an image."""
    out = _sips(["-g", "pixelWidth", "-g", "pixelHeight", path])
    found = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in ("pixelWidth", "pixelHeight"):
            found[key] = int(value.strip())
    if "pixelWidth" not in found or "pixelHeight" not in found:
        raise SipsError("no pixel dimensions in sips output for %s" % path)
    return (found["pixelWidth"], found["pixelHeight"])


def to_jpeg(src, dst, max_px, quality):
    """Convert src to a JPEG at dst, fitting the long edge within max_px.

    Measured on sips-316: `-Z` UPSCALES a smaller source -- a 64x48 image
    at `-Z 4000` comes back 4000x3000 and 190 KB. That is pure waste, and
    the archive does contain small screenshots and JFIF captures alongside
    the 5472x3648 Canon originals. So clamp the target to the source's own
    long edge and let small images through untouched.

    Returns {"w", "h", "bytes"}.
    """
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    src_w, src_h = dimensions(src)
    target = min(max_px, max(src_w, src_h))
    _sips(["-s", "format", "jpeg",
           "-s", "formatOptions", str(quality),
           "-Z", str(target),
           src, "--out", dst])
    w, h = dimensions(dst)
    return {"w": w, "h": h, "bytes": os.path.getsize(dst)}


def web(src, dst):
    return to_jpeg(src, dst, WEB_MAX_PX, WEB_QUALITY)


def thumb(src, dst):
    return to_jpeg(src, dst, THUMB_MAX_PX, THUMB_QUALITY)
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_images -v`
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/images.py tools/tests/test_images.py
git commit -m "$(printf 'feat: add sips image pipeline wrapper\n\nsips is the only image tool on this machine (no Pillow, ImageMagick or\ncwebp) and it cannot write WebP, so all output is JPEG. Sizes are the\nmeasured ones: 1400px/q68 for web, 480px/q70 for thumbnails.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: `tools/addresses.py` — before/after pair matching

32 real pairs exist, found by normalizing street addresses out of folder and file names that never agree on formatting: `2251 86th St` vs `George Hall, MD - 2251 86th St`, `142-18 38th Ave` vs `14218 38th`.

**Files:**
- Create: `tools/addresses.py`
- Create: `tools/tests/test_addresses.py`

**Interfaces:**
- Consumes: `fixtures.ArchiveFixture`
- Produces:
  - `addresses.normalize(name: str) -> Optional[str]` — e.g. `"Dr. Hall - 2251 86th St"` → `"2251 86th"`; `None` when no address is present
  - `addresses.collect_before(root: str) -> Dict[str, List[str]]` — address → paths, across `_Original Excelsior Photos/` (folders) and `_Original Legacy Rendr Photo/` (files)
  - `addresses.collect_after(root: str) -> Dict[str, List[str]]` — address → paths under `_Completed Installation Photos/`
  - `addresses.match_pairs(root: str) -> List[dict]` — sorted list of `{"address", "before_dir", "after_dir", "label"}`; `label` is a human string like `"2251 86th St"` taken from the after-side folder

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_addresses.py
import unittest

from tools import addresses
from tools.tests import fixtures


class TestNormalize(unittest.TestCase):
    def test_strips_a_leading_practice_name(self):
        self.assertEqual(addresses.normalize("Dr. Hall - 2251 86th St"), "2251 86th")

    def test_matches_the_same_address_written_two_ways(self):
        self.assertEqual(
            addresses.normalize("Zhengbo Huang, MD - 142-18 38th Ave"),
            addresses.normalize("Dr. Zhengbo Huang - 142-18 38th Ave"),
        )

    def test_ignores_hyphens_inside_the_house_number(self):
        self.assertEqual(addresses.normalize("136-20 38th St"), "13620 38th")

    def test_ignores_suite_and_floor_suffixes(self):
        self.assertEqual(
            addresses.normalize("Dr. Henry Chen - 128 Mott ST 308"),
            addresses.normalize("Oncology - 128 Mott St. Suite 309"),
        )

    def test_returns_none_without_an_address(self):
        self.assertIsNone(addresses.normalize("Lunar New Year 2024"))

    def test_handles_a_filename_with_an_extension_and_descriptor(self):
        self.assertEqual(
            addresses.normalize("7217 18th Ave - Logo.png"), "7217 18th"
        )


class TestMatching(fixtures.ArchiveFixture, unittest.TestCase):
    def test_finds_the_three_planted_pairs(self):
        pairs = addresses.match_pairs(self.archive_root)
        found = sorted(p["address"] for p in pairs)
        self.assertEqual(found, ["14218 38th", "2251 86th", "94 bowery"])

    def test_excludes_before_only_and_after_only_locations(self):
        pairs = addresses.match_pairs(self.archive_root)
        joined = " ".join(p["before_dir"] + p["after_dir"] for p in pairs)
        self.assertNotIn("Nowhere", joined)
        self.assertNotIn("Elsewhere", joined)

    def test_each_pair_carries_both_sides_and_a_label(self):
        pair = addresses.match_pairs(self.archive_root)[0]
        for key in ("address", "before_dir", "after_dir", "label"):
            self.assertIn(key, pair)
            self.assertTrue(pair[key])

    def test_legacy_rendr_files_contribute_before_entries(self):
        before = addresses.collect_before(self.archive_root)
        self.assertIn("7217 18th", before)
```

One rule throughout: the house number always has its hyphens stripped, so `142-18 38th Ave` and `136-20 38th St` both normalize to a digits-only number.

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_addresses -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.addresses'`

- [ ] **Step 3: Implement it**

```python
# tools/addresses.py
"""Match pre-rebrand signage folders to post-rebrand ones by street address.

Folder names agree on nothing: "George Hall, MD - 2251 86th St",
"Dr. Hall - 2251 86th St", "136-20 38th St", "Oncology - 128 Mott St. Suite 309".
normalize() reduces each to "<housenumber> <streetword>", which is the
narrowest key that still separates distinct locations in this archive.
"""
import os
import re

BEFORE_TOPS = ("_Original Excelsior Photos", "_Original Legacy Rendr Photo")
AFTER_TOP = "_Completed Installation Photos"

# Dropped before matching: practice/person prefix up to a dash, and any
# suite/floor/unit tail. Both vary freely between the two sides.
_PREFIX = re.compile(r"^.*?[-–]\s*")
_SUFFIX = re.compile(
    r"\s*(#|ste\b|suite\b|fl\b|floor\b|\d+(st|nd|rd|th)?\s*fl\b|apt\b|unit\b).*$",
    re.I,
)
_ADDRESS = re.compile(r"^([\d\-]+)\s+([a-z0-9]+)")


def normalize(name):
    """Return "<housenumber> <streetword>", or None if there is no address."""
    s = name.lower()
    s = os.path.splitext(s)[0]
    s = s.split("(")[0]
    # A trailing " - Logo", " - Interior Logo" etc. is a photo descriptor.
    s = re.sub(r"\s*-\s*(exterior|interior|entrance|hallway|front|building|waiting|floor)\b.*$", "", s)
    s = re.sub(r"\s*-\s*[a-z ]*logo\s*$", "", s)
    s = re.sub(r"\s*-\s*[a-z ]*directory\s*$", "", s)
    s = _SUFFIX.sub("", s)
    candidate = _ADDRESS.match(s.strip())
    if not candidate:
        stripped = _PREFIX.sub("", s, count=1).strip()
        candidate = _ADDRESS.match(stripped)
    if not candidate:
        return None
    number = candidate.group(1).replace("-", "")
    street = candidate.group(2)
    return "%s %s" % (number, street)


def _add(mapping, key, path):
    if key:
        mapping.setdefault(key, []).append(path)


def collect_before(root):
    """Address -> paths. Excelsior stores one folder per location; Legacy
    Rendr stores loose files whose names carry the address."""
    out = {}
    for top in BEFORE_TOPS:
        base = os.path.join(root, top)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            for d in dirnames:
                _add(out, normalize(d), os.path.join(dirpath, d))
            for f in filenames:
                if f.startswith("."):
                    continue
                _add(out, normalize(f), os.path.join(dirpath, f))
    return out


def collect_after(root):
    out = {}
    base = os.path.join(root, AFTER_TOP)
    if not os.path.isdir(base):
        return out
    for d in sorted(os.listdir(base)):
        full = os.path.join(base, d)
        if os.path.isdir(full):
            _add(out, normalize(d), full)
    return out


def _label(after_dir):
    """Human label: the address portion of the after-side folder name."""
    name = os.path.basename(after_dir)
    return _PREFIX.sub("", name, count=1).strip() or name


def match_pairs(root):
    before = collect_before(root)
    after = collect_after(root)
    pairs = []
    for address in sorted(set(before) & set(after)):
        pairs.append({
            "address": address,
            "before_dir": sorted(before[address])[0],
            "after_dir": sorted(after[address])[0],
            "label": _label(sorted(after[address])[0]),
        })
    return pairs
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_addresses -v`
Expected: PASS, 10 tests.

- [ ] **Step 5: Verify against the real archive, read-only**

Run:
```bash
python3 -c "
from tools import addresses
r='/Users/weizhang/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos'
p=addresses.match_pairs(r)
print(len(p),'pairs')
for x in p[:5]: print(' ',x['label'],'|',x['address'])
"
```
Expected: around 32 pairs. This only lists directory names, so it downloads nothing. If the count is far below 32, print `set(collect_before) ^ set(collect_after)` and widen the suffix rules.

- [ ] **Step 6: Commit**

```bash
git add tools/addresses.py tools/tests/test_addresses.py
git commit -m "$(printf 'feat: match rebrand before/after locations by address\n\nThe pre-rebrand (Excelsior, Legacy Rendr) and post-rebrand (Completed\nInstallation) folders name the same clinic completely differently.\nNormalizing to "<housenumber> <streetword>" recovers 32 matched pairs,\nwhich is the evidence behind the site 88%% brand-awareness claim.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: `tools/build_rebrand.py` — publish the featured pairs

First task that downloads anything. It hydrates only the chosen pairs: 2 photos each, so ~10 files for 5 pairs.

**Files:**
- Create: `tools/build_rebrand.py`
- Create: `tools/tests/test_build_rebrand.py`

**Interfaces:**
- Consumes: `addresses.match_pairs`, `images.web`, `images.SipsError`
- Produces:
  - `build_rebrand.slugify(text: str) -> str` — `"2251 86th St"` → `"2251-86th-st"`
  - `build_rebrand.pick_photo(folder: str) -> Optional[str]` — the largest image file in `folder`, by logical size; `None` if the folder holds no image
  - `build_rebrand.build(archive: str, out_dir: str, assets_dir: str, limit: int) -> dict` — returns `{"pairs": List[dict], "published": List[dict], "skipped": List[dict]}`; each published entry is `{"slug", "label", "before", "after", "w", "h"}` where `before`/`after` are repo-relative asset paths
  - `build_rebrand.html_snippet(published: List[dict]) -> str` — the markup block for Task 5
  - CLI: `python3 -m tools.build_rebrand --archive PATH [--limit 5]`

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_build_rebrand.py
import json
import os
import unittest

from tools import build_rebrand
from tools.tests import fixtures


class TestSlugify(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(build_rebrand.slugify("2251 86th St"), "2251-86th-st")

    def test_collapses_punctuation_and_runs(self):
        self.assertEqual(build_rebrand.slugify("Dr. Hall  --  94 Bowery!"),
                         "dr-hall-94-bowery")

    def test_never_starts_or_ends_with_a_hyphen(self):
        slug = build_rebrand.slugify("  -- 94 Bowery -- ")
        self.assertFalse(slug.startswith("-"))
        self.assertFalse(slug.endswith("-"))


class TestPickPhoto(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_picks_the_largest_image(self):
        small = fixtures.make_seed_image(os.path.join(self.tmp, "small.jpg"), "jpg")
        big = os.path.join(self.tmp, "big.jpg")
        with open(small, "rb") as fh:
            data = fh.read()
        with open(big, "wb") as fh:
            fh.write(data + b"\x00" * 5000)
        self.assertEqual(build_rebrand.pick_photo(self.tmp), big)

    def test_ignores_non_images_and_dotfiles(self):
        with open(os.path.join(self.tmp, ".DS_Store"), "w") as fh:
            fh.write("x" * 9999)
        with open(os.path.join(self.tmp, "notes.txt"), "w") as fh:
            fh.write("x" * 9999)
        jpg = fixtures.make_seed_image(os.path.join(self.tmp, "a.jpg"), "jpg")
        self.assertEqual(build_rebrand.pick_photo(self.tmp), jpg)

    def test_returns_none_for_an_empty_folder(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        self.assertIsNone(build_rebrand.pick_photo(empty))


class TestBuild(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        self.out = os.path.join(self.work, "out")
        self.assets = os.path.join(self.work, "assets", "rebrand")

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def test_writes_a_json_file_with_every_matched_pair(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=2)
        path = os.path.join(self.out, "rebrand-pairs.json")
        with open(path) as fh:
            data = json.load(fh)
        self.assertEqual(len(data["pairs"]), 3)      # fixture plants 3 matches
        self.assertEqual(len(result["published"]), 2)  # limit honored

    def test_publishes_two_jpegs_per_pair(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=2)
        for entry in result["published"]:
            for key in ("before", "after"):
                disk = os.path.join(self.work, entry[key])
                self.assertTrue(os.path.exists(disk), entry[key])
                with open(disk, "rb") as fh:
                    self.assertEqual(fh.read(2), b"\xff\xd8")

    def test_published_paths_are_repo_relative(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=1)
        entry = result["published"][0]
        self.assertTrue(entry["before"].startswith("assets/rebrand/"))
        self.assertFalse(os.path.isabs(entry["before"]))

    def test_records_pixel_dimensions(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=1)
        entry = result["published"][0]
        self.assertGreater(entry["w"], 0)
        self.assertGreater(entry["h"], 0)

    def test_does_not_modify_the_archive(self):
        before = sorted(
            os.path.join(dp, f)
            for dp, dn, fn in os.walk(self.archive_root) for f in fn
        )
        build_rebrand.build(self.archive_root, self.out, self.assets, limit=3)
        after = sorted(
            os.path.join(dp, f)
            for dp, dn, fn in os.walk(self.archive_root) for f in fn
        )
        self.assertEqual(before, after)

    def test_snippet_contains_one_pair_block_per_published_pair(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=2)
        html = build_rebrand.html_snippet(result["published"])
        self.assertEqual(html.count("data-ba-pair"), 2)
        self.assertIn('class="ba-pair active"', html)
        self.assertIn("data-slot=", html)   # keeps the placeholder fallback
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_build_rebrand -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.build_rebrand'`

- [ ] **Step 3: Implement it**

```python
# tools/build_rebrand.py
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
    """Largest image in folder, by logical size. Largest is the best proxy
    for highest quality here; the archive mixes phone and DSLR shots."""
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


def build(archive, out_dir, assets_dir, limit=5):
    """Match every pair, publish the first `limit` of them."""
    pairs = addresses.match_pairs(archive)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)
    assets_rel = "assets/rebrand"

    published = []
    skipped = []
    for pair in pairs:
        if len(published) >= limit:
            break
        before_src = pick_photo(pair["before_dir"])
        after_src = pick_photo(pair["after_dir"])
        if not before_src or not after_src:
            skipped.append({"label": pair["label"], "why": "no image on one side"})
            continue
        slug = slugify(pair["label"])
        try:
            before_rel, info = _side(before_src, assets_dir, assets_rel, slug, "before")
            after_rel, _ = _side(after_src, assets_dir, assets_rel, slug, "after")
        except images.SipsError as exc:
            skipped.append({"label": pair["label"], "why": str(exc)})
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
    ap.add_argument("--out", default="tools/out")
    ap.add_argument("--assets", default="assets/rebrand")
    args = ap.parse_args(argv)

    result = build(args.archive, args.out, args.assets, args.limit)
    print("matched %d pairs, published %d, skipped %d"
          % (len(result["pairs"]), len(result["published"]), len(result["skipped"])))
    for s in result["skipped"]:
        print("  skipped %s: %s" % (s["label"], s["why"]))
    print("\n--- paste into index.html ---\n")
    print(html_snippet(result["published"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_build_rebrand -v`
Expected: PASS, 12 tests.

- [ ] **Step 5: Run it against the real archive**

```bash
python3 -m tools.build_rebrand \
  --archive "$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos" \
  --limit 5
du -sh assets/rebrand; ls -lh assets/rebrand
```
Expected: "matched 32 pairs, published 5". 10 JPEGs, each well under 500 KB. The first run is slow because each source file hydrates from the cloud on read. If a file errors with a download failure, re-run — `sips` will retry the fetch.

Keep the printed snippet; Task 5 pastes it.

- [ ] **Step 6: Commit**

```bash
git add tools/build_rebrand.py tools/tests/test_build_rebrand.py assets/rebrand
git commit -m "$(printf 'feat: publish featured rebrand before/after pairs\n\nHydrates only the chosen pairs (about 2 files each) rather than the\n45 GB archive, converts them to 1400px JPEGs, and records all 32 matches\nin tools/out/rebrand-pairs.json for later use.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: Case Study 02 before/after component

This is the first user-visible change and it closes the site's only known content gap. Today [`index.html:156-159`](../../../index.html#L156-L159) points at `assets/rebrand_before.jpg` and `assets/rebrand_after.jpg`, which do not exist, so `script.js` swaps both for grey labeled placeholder boxes.

**Files:**
- Modify: `index.html:156-159` (the `.beforeafter` block)
- Modify: `style.css` (append the `.ba-*` rules)
- Modify: `script.js` (add the carousel; also add the null guards every page needs)
- Modify: `README.md` (image table)

**Interfaces:**
- Consumes: `build_rebrand.html_snippet` output from Task 4, and `assets/rebrand/*.jpg`
- Produces: DOM contract `[data-ba]` wrapper containing `[data-ba-pair]` children, `[data-ba-label]`, `[data-ba-dots]`, `.ba-prev`, `.ba-next`. Task 15 relies on none of this; it is self-contained.

- [ ] **Step 1: Replace the markup**

Replace lines 156-159 of `index.html` (the whole `<div class="beforeafter">…</div>`) with the structure below, substituting the 5 pair blocks printed by Task 4 Step 5 where marked:

```html
          <div class="beforeafter" data-ba>
            <div class="ba-head">
              <button type="button" class="ba-nav ba-prev" aria-label="Previous location">◀</button>
              <span class="ba-label" data-ba-label>2251 86th St</span>
              <button type="button" class="ba-nav ba-next" aria-label="Next location">▶</button>
            </div>
            <div class="ba-pairs">
<!-- PASTE the 5 data-ba-pair blocks from tools.build_rebrand here -->
            </div>
            <div class="ba-dots" data-ba-dots aria-hidden="true"></div>
            <p class="ba-note">5 of 32 matched locations across the rollout</p>
          </div>
```

- [ ] **Step 2: Append the styles**

Append to `style.css`. These reuse the existing tokens, and the first-child rule is what makes the component work before JavaScript runs:

```css
/* Before/after comparison (Case 02) */
.ba-head { display: flex; align-items: center; justify-content: space-between; gap: .5rem; margin-bottom: .6rem; }
.ba-label { font-weight: 600; font-size: .95rem; }
.ba-nav { background: var(--accent-soft); color: var(--accent); border: 1px solid var(--line); border-radius: 999px; width: 2rem; height: 2rem; cursor: pointer; line-height: 1; }
.ba-nav:hover { background: var(--accent); color: var(--accent-text); }
.ba-nav:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.ba-pair { display: none; grid-template-columns: 1fr 1fr; gap: .75rem; }
.ba-pair:first-child { display: grid; }
.ba-pairs[data-ba-ready] .ba-pair { display: none; }
.ba-pairs[data-ba-ready] .ba-pair.active { display: grid; }
.ba-pair figure { margin: 0; }
.ba-pair img, .ba-pair .slot { width: 100%; aspect-ratio: 3 / 4; object-fit: cover; border-radius: 14px; }
.ba-pair figcaption { font-weight: 600; margin-top: .35rem; }
.ba-dots { display: flex; gap: .4rem; justify-content: center; margin-top: .7rem; }
.ba-dot { width: .5rem; height: .5rem; border-radius: 999px; border: 0; padding: 0; background: var(--line); cursor: pointer; }
.ba-dot[aria-current="true"] { background: var(--accent); }
.ba-note { color: var(--muted); font-size: .85rem; text-align: center; margin-top: .5rem; }
@media (max-width: 720px) {
  .ba-pair, .ba-pairs[data-ba-ready] .ba-pair.active { grid-template-columns: 1fr 1fr; }
  .ba-pair img, .ba-pair .slot { aspect-ratio: 1 / 1; }
}
```

- [ ] **Step 3: Add the behavior, and guard the shared script**

Replace the first line of `script.js` and the two unguarded `querySelector` blocks so the file is safe on every page, then append the carousel:

```javascript
// Footer year
const yearEl = document.getElementById("year");
if (yearEl) yearEl.textContent = new Date().getFullYear();
```

```javascript
// Theme toggle (remembered per browser)
const root = document.documentElement;
try {
  const saved = localStorage.getItem("theme");
  if (saved) root.dataset.theme = saved;
} catch {}
const themeBtn = document.querySelector(".theme-toggle");
if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    const isDark = root.dataset.theme
      ? root.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = isDark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch {}
  });
}
```

```javascript
// Mobile menu
const toggle = document.querySelector(".nav-toggle");
const links = document.querySelector(".nav-links");
if (toggle && links) {
  toggle.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open);
  });
  links.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", () => links.classList.remove("open"))
  );
}
```

Append:

```javascript
// Before/after comparison: markup ships all pairs; JS only switches which is shown.
document.querySelectorAll("[data-ba]").forEach((ba) => {
  const wrap = ba.querySelector(".ba-pairs");
  const pairs = [...ba.querySelectorAll("[data-ba-pair]")];
  const label = ba.querySelector("[data-ba-label]");
  const dots = ba.querySelector("[data-ba-dots]");
  if (!wrap || pairs.length === 0) return;

  let index = 0;
  const show = (next) => {
    index = (next + pairs.length) % pairs.length;
    pairs.forEach((p, i) => p.classList.toggle("active", i === index));
    if (label) label.textContent = pairs[index].dataset.label || "";
    if (dots) {
      [...dots.children].forEach((d, i) =>
        d.setAttribute("aria-current", String(i === index))
      );
    }
  };

  if (dots) {
    pairs.forEach((p, i) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "ba-dot";
      dot.setAttribute("aria-label", `Show ${p.dataset.label || `location ${i + 1}`}`);
      dot.addEventListener("click", () => show(i));
      dots.append(dot);
    });
    dots.removeAttribute("aria-hidden");
  }

  const prev = ba.querySelector(".ba-prev");
  const next = ba.querySelector(".ba-next");
  if (prev) prev.addEventListener("click", () => show(index - 1));
  if (next) next.addEventListener("click", () => show(index + 1));
  ba.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") show(index - 1);
    if (e.key === "ArrowRight") show(index + 1);
  });

  wrap.dataset.baReady = "1";
  show(0);
});
```

- [ ] **Step 4: Verify it in a browser**

```bash
open index.html
```
Check, in this order:
1. Case 02 shows a real before photo and a real after photo, not grey placeholder boxes.
2. `◀` / `▶` and the 5 dots switch locations, and the label text changes with them.
3. Toggle dark mode — borders and dots still read correctly.
4. Narrow the window to 375px — two images stay side by side, no horizontal page scroll.
5. Open DevTools console — no errors.
6. Disable JavaScript and reload — the first pair is still visible.

- [ ] **Step 5: Update the README image table**

Change the `rebrand_before.jpg` / `rebrand_after.jpg` row to:

```markdown
| `rebrand/*-before.jpg`, `rebrand/*-after.jpg` | ✅ 5 featured before/after signage pairs, matched by address from OneDrive (32 pairs available, see `tools/out/rebrand-pairs.json`) |
```

- [ ] **Step 6: Commit**

```bash
git add index.html style.css script.js README.md
git commit -m "$(printf 'feat: add switchable before/after comparison to Case 02\n\nReplaces the two missing rebrand images, which script.js had been\nswapping for grey placeholder boxes, with 5 real matched pairs out of the\n32 found in the archive. All pairs ship as markup so the component still\nshows a pair with JavaScript disabled.\n\nAlso guards script.js lookups for #year, .theme-toggle and .nav-toggle,\nwhich previously threw on any page lacking them -- events.html will.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: `tools/naming.py` — date parsing across 8 formats

The archive uses `0512`, `06102023`, `231113`, `11.23.23`, `12-16-2023`, `5.8.25`, `3.29`, `5 .7`, `Mar2025`, `_05082025` and bare `April Event`. Sorting is impossible until these collapse to ISO.

**Files:**
- Create: `tools/naming.py`
- Create: `tools/tests/test_naming.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `naming.parse_date(name: str, year_hint: Optional[int]) -> Optional[dict]` — `{"iso": "2023-11-13", "pattern": "YYMMDD", "token": "231113"}`, or `None`
  - `naming.clean_title(name: str) -> str` — the name with its date token and separators removed
  - `naming.slugify(text: str) -> str`
  - `naming.proposed_name(name: str, year_hint: Optional[int]) -> str` — `"2023-11-13 Centerlight Health Fair"`, or `"2024 Lunar New Year"` when only a year is known, or the original name when nothing parses
  - `naming.find_conflicts(entries: List[dict]) -> List[dict]` — `entries` are `{"name", "iso", "path"}`; returns `{"title", "dates", "paths"}` for titles carrying more than one date

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_naming.py
import unittest

from tools import naming


class TestParseDate(unittest.TestCase):
    def check(self, name, expected_iso, year_hint=None):
        got = naming.parse_date(name, year_hint)
        self.assertIsNotNone(got, "failed to parse %r" % name)
        self.assertEqual(got["iso"], expected_iso, name)

    def test_mmdd_with_year_from_parent_folder(self):
        self.check("0512 Blood Pressure Seminar Flushing", "2022-05-12", 2022)
        self.check("1016 Breast Cancer Walk", "2022-10-16", 2022)

    def test_mmddyyyy_run_together(self):
        self.check("06102023 CAS Award Gala", "2023-06-10")
        self.check("10182023 Bay ST Grand Opening", "2023-10-18")

    def test_yymmdd(self):
        self.check("231113 Centerlight Health Fair", "2023-11-13")

    def test_dotted_two_digit_year(self):
        self.check("11.23.23 Centerlight Health Fair", "2023-11-23")
        self.check("5.8.25 Rendr Flushing STEB Grand Opening", "2025-05-08")

    def test_dotted_four_digit_year(self):
        self.check("3.27.2026 - Dr. Daniel Yeoun's Colorectal Cancer Seminar", "2026-03-27")

    def test_dotted_no_year_uses_hint(self):
        self.check("3.29 Dr. David Zhuang Health Talk", "2025-03-29", 2025)
        self.check("12.12 Dr. Xian Cheung ACAP Heath Seminar", "2025-12-12", 2025)

    def test_hyphenated_date_at_the_end(self):
        self.check("Provider Holiday Party 12-16-2023", "2023-12-16")

    def test_trailing_underscore_date(self):
        self.check("Flushing Basement Grand Opening_05082025", "2025-05-08")

    def test_stray_space_inside_the_date(self):
        self.check("UHC Golf Outing 5 .7", "2025-05-07", 2025)

    def test_month_name_and_year(self):
        self.check("Chinatown Open House with UHC_Mar2025", "2025-03-01")

    def test_returns_none_when_there_is_no_date(self):
        self.assertIsNone(naming.parse_date("Lunar New Year 2024", None))
        self.assertIsNone(naming.parse_date("Brain Health Day at CCBA", None))

    def test_rejects_impossible_dates(self):
        self.assertIsNone(naming.parse_date("9999 Nonsense", None))
        self.assertIsNone(naming.parse_date("1332 Bad Month", 2022))


class TestTitlesAndNames(unittest.TestCase):
    def test_clean_title_drops_the_date_token(self):
        self.assertEqual(
            naming.clean_title("0512 Blood Pressure Seminar Flushing"),
            "Blood Pressure Seminar Flushing",
        )

    def test_clean_title_drops_a_trailing_date_and_separator(self):
        self.assertEqual(
            naming.clean_title("Provider Holiday Party 12-16-2023"),
            "Provider Holiday Party",
        )

    def test_clean_title_drops_the_dash_after_a_2026_style_date(self):
        self.assertEqual(
            naming.clean_title("3.1.2026 - Chinatown LNY Parade"),
            "Chinatown LNY Parade",
        )

    def test_clean_title_collapses_double_spaces(self):
        self.assertEqual(naming.clean_title("UCA (Cultural)  Event"), "UCA (Cultural) Event")

    def test_proposed_name_is_iso_first(self):
        self.assertEqual(
            naming.proposed_name("0512 Blood Pressure Seminar Flushing", 2022),
            "2022-05-12 Blood Pressure Seminar Flushing",
        )

    def test_proposed_name_falls_back_to_year_only(self):
        self.assertEqual(
            naming.proposed_name("Lunar New Year 2024", 2024),
            "2024 Lunar New Year 2024",
        )

    def test_proposed_name_returns_input_when_nothing_is_known(self):
        self.assertEqual(naming.proposed_name("Mystery Folder", None), "Mystery Folder")

    def test_slugify(self):
        self.assertEqual(naming.slugify("Dr. Xian Cheung's Diabetes Seminar"),
                         "dr-xian-cheung-s-diabetes-seminar")


class TestConflicts(unittest.TestCase):
    def test_flags_one_title_carrying_two_dates(self):
        entries = [
            {"name": "11.23.23 Centerlight Health Fair", "iso": "2023-11-23", "path": "a"},
            {"name": "231113 Centerlight Health Fair", "iso": "2023-11-13", "path": "b"},
        ]
        conflicts = naming.find_conflicts(entries)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(sorted(conflicts[0]["dates"]), ["2023-11-13", "2023-11-23"])
        self.assertEqual(sorted(conflicts[0]["paths"]), ["a", "b"])

    def test_quiet_when_dates_agree(self):
        entries = [
            {"name": "231113 Centerlight Health Fair", "iso": "2023-11-13", "path": "a"},
            {"name": "11.13.23 Centerlight Health Fair", "iso": "2023-11-13", "path": "b"},
        ]
        self.assertEqual(naming.find_conflicts(entries), [])
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_naming -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.naming'`

- [ ] **Step 3: Implement it**

```python
# tools/naming.py
"""Normalize event folder names to "YYYY-MM-DD Title".

The archive carries ten distinct date spellings. Each pattern below is
anchored and validated through datetime, so an impossible date falls through
to the next pattern rather than producing a wrong answer.
"""
import datetime
import re

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# (pattern name, compiled regex, builder) tried in order. More specific first:
# an 8-digit run must be read as MMDDYYYY before a 4-digit MMDD can match it.
_PATTERNS = []


def _p(name, regex, builder):
    _PATTERNS.append((name, re.compile(regex, re.I), builder))


def _valid(y, m, d):
    try:
        return datetime.date(y, m, d).isoformat()
    except ValueError:
        return None


def _yy(value):
    """Two-digit year -> 2000s. The archive starts in 2022."""
    return 2000 + int(value)


_p("MMDDYYYY", r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)",
   lambda m, hint: _valid(int(m.group(3)), int(m.group(1)), int(m.group(2))))
_p("M.D.YYYY", r"(?<!\d)(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(20\d{2})(?!\d)",
   lambda m, hint: _valid(int(m.group(3)), int(m.group(1)), int(m.group(2))))
_p("M.D.YY", r"(?<!\d)(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{2})(?!\d)",
   lambda m, hint: _valid(_yy(m.group(3)), int(m.group(1)), int(m.group(2))))
_p("YYMMDD", r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)",
   lambda m, hint: _valid(_yy(m.group(1)), int(m.group(2)), int(m.group(3))))
_p("MonYYYY", r"(?<![a-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(20\d{2})(?!\d)",
   lambda m, hint: _valid(int(m.group(2)), MONTHS[m.group(1).lower()], 1))
_p("M.D", r"(?<!\d)(\d{1,2})\s*[.]\s*(\d{1,2})(?!\d)",
   lambda m, hint: _valid(hint, int(m.group(1)), int(m.group(2))) if hint else None)
_p("MMDD", r"(?<!\d)(\d{2})(\d{2})(?!\d)",
   lambda m, hint: _valid(hint, int(m.group(1)), int(m.group(2))) if hint else None)


def parse_date(name, year_hint=None):
    """First pattern that yields a real calendar date wins."""
    for pattern, regex, build in _PATTERNS:
        for match in regex.finditer(name):
            iso = build(match, year_hint)
            if iso:
                return {"iso": iso, "pattern": pattern, "token": match.group(0)}
    return None


def clean_title(name):
    """Name with its date token, surrounding separators and noise removed."""
    found = parse_date(name, 2000)   # any hint: we only want the token span
    text = name
    if found:
        text = text.replace(found["token"], " ", 1)
    text = re.sub(r"^[\s_\-–.]+", "", text)
    text = re.sub(r"[\s_\-–.]+$", "", text)
    text = re.sub(r"^[-–]\s*", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def proposed_name(name, year_hint=None):
    found = parse_date(name, year_hint)
    title = clean_title(name)
    if found:
        return "%s %s" % (found["iso"], title)
    year_in_name = re.search(r"(20\d{2})", name)
    year = year_in_name.group(1) if year_in_name else (str(year_hint) if year_hint else None)
    if year:
        return "%s %s" % (year, title)
    return name


def find_conflicts(entries):
    """Same title, different dates -> the archive disagrees with itself."""
    by_title = {}
    for entry in entries:
        key = slugify(clean_title(entry["name"]))
        by_title.setdefault(key, []).append(entry)
    conflicts = []
    for key in sorted(by_title):
        group = by_title[key]
        dates = sorted({e["iso"] for e in group if e.get("iso")})
        if len(dates) > 1:
            conflicts.append({
                "title": clean_title(group[0]["name"]),
                "dates": dates,
                "paths": sorted(e["path"] for e in group),
            })
    return conflicts
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_naming -v`
Expected: PASS, 22 tests. If `test_month_name_and_year` fails, confirm `MonYYYY` is ordered before `M.D`; `Mar2025` contains no dotted date so ordering only matters for safety.

- [ ] **Step 5: Commit**

```bash
git add tools/naming.py tools/tests/test_naming.py
git commit -m "$(printf 'feat: parse the ten date spellings used in the archive\n\nEvery pattern is validated through datetime, so an impossible reading\n(month 23, day 32) falls through to the next pattern instead of producing\na wrong date. find_conflicts surfaces the Centerlight case, where one\nevent is filed under both 11.23.23 and 231113.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: `tools/scan.py` — read-only inventory

**Files:**
- Create: `tools/scan.py`
- Create: `tools/tests/test_scan.py`

**Interfaces:**
- Consumes: `fixtures.ArchiveFixture`
- Produces:
  - `scan.CATCHALLS = ("2022", "2023", "2024 Events1", "2025 Events1", "archive")`
  - `scan.classify_path(rel: str) -> dict` — `{"top", "year", "event", "catchall": bool}`; `year` and `event` may be `None`
  - `scan.walk(root: str) -> Iterator[dict]` — one dict per file: `{"rel", "path", "top", "year", "event", "catchall", "name", "ext", "bytes", "hydrated"}`
  - `scan.write_inventory(root: str, csv_path: str) -> dict` — writes the CSV, returns `{"files", "bytes", "hydrated", "hydrated_bytes", "events"}`
  - CLI: `python3 -m tools.scan --archive PATH [--out tools/out]`

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_scan.py
import csv
import os
import unittest

from tools import scan
from tools.tests import fixtures


class TestClassifyPath(unittest.TestCase):
    def test_plain_event(self):
        got = scan.classify_path("Event Photos/2022 Events/1023 Rendr Dinner/IMG_0001.jpg")
        self.assertEqual(got["year"], "2022 Events")
        self.assertEqual(got["event"], "1023 Rendr Dinner")
        self.assertFalse(got["catchall"])

    def test_event_inside_a_catchall(self):
        got = scan.classify_path(
            "Event Photos/2022 Events/2022/1023 Rendr Dinner/IMG_0001.jpg")
        self.assertEqual(got["event"], "1023 Rendr Dinner")
        self.assertTrue(got["catchall"])

    def test_archive_catchall_is_recognized(self):
        got = scan.classify_path(
            "Event Photos/2025 Events/archive/0812 ROAR Chinatown Community Event/a.jpg")
        self.assertEqual(got["event"], "0812 ROAR Chinatown Community Event")
        self.assertTrue(got["catchall"])

    def test_2026_month_layer_is_skipped(self):
        got = scan.classify_path(
            "Event Photos/2026 Event/June Event/6.9.2026 - Diabetes Seminar/a.jpg")
        self.assertEqual(got["year"], "2026 Event")
        self.assertEqual(got["event"], "6.9.2026 - Diabetes Seminar")
        self.assertFalse(got["catchall"])

    def test_signage_folders_have_no_year(self):
        got = scan.classify_path(
            "_Completed Installation Photos/Dr. Hall - 2251 86th St/a.jfif")
        self.assertEqual(got["top"], "_Completed Installation Photos")
        self.assertIsNone(got["year"])
        self.assertEqual(got["event"], "Dr. Hall - 2251 86th St")


class TestWalk(fixtures.ArchiveFixture, unittest.TestCase):
    def test_finds_every_file_and_skips_dotfiles(self):
        with open(os.path.join(self.archive_root, "Event Photos", ".DS_Store"), "w") as fh:
            fh.write("x")
        rows = list(scan.walk(self.archive_root))
        self.assertEqual(len(rows), self.archive_stats["files"])
        self.assertFalse(any(r["name"].startswith(".") for r in rows))

    def test_records_size_and_extension(self):
        row = next(r for r in scan.walk(self.archive_root) if r["ext"] == "heic")
        self.assertGreater(row["bytes"], 0)
        self.assertEqual(row["ext"], "heic")

    def test_marks_local_fixture_files_as_hydrated(self):
        # Fixture files are real local files, so st_blocks > 0 for all of them.
        rows = list(scan.walk(self.archive_root))
        self.assertTrue(all(r["hydrated"] for r in rows))

    def test_never_opens_a_file(self):
        opened = []
        real_open = open

        def spy(path, *a, **k):
            opened.append(path)
            return real_open(path, *a, **k)

        import builtins
        builtins.open = spy
        try:
            list(scan.walk(self.archive_root))
        finally:
            builtins.open = real_open
        under_archive = [p for p in opened if str(p).startswith(self.archive_root)]
        self.assertEqual(under_archive, [])


class TestWriteInventory(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def test_writes_one_row_per_file_with_a_header(self):
        path = os.path.join(self.work, "inventory.csv")
        stats = scan.write_inventory(self.archive_root, path)
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), self.archive_stats["files"])
        self.assertEqual(stats["files"], self.archive_stats["files"])
        for field in ("rel", "top", "year", "event", "catchall", "ext", "bytes", "hydrated"):
            self.assertIn(field, rows[0])

    def test_counts_distinct_events(self):
        stats = scan.write_inventory(
            self.archive_root, os.path.join(self.work, "inventory.csv"))
        self.assertGreater(stats["events"], 0)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_scan -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.scan'`

- [ ] **Step 3: Implement it**

```python
# tools/scan.py
"""Read-only inventory of the archive.

Uses os.scandir and os.stat only. It never opens a file body, so it triggers
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
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_scan -v`
Expected: PASS, 11 tests. `test_never_opens_a_file` is the important one — it is the guard that keeps a scan from pulling 45 GB.

- [ ] **Step 5: Run it against the real archive**

```bash
python3 -m tools.scan --archive "$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos"
wc -l tools/out/inventory.csv
```
Expected: around 9,073 files and 45.4 GB. The file count will have grown if sync has added anything; that is fine. The run should finish in seconds — if it stalls, something is reading bytes.

- [ ] **Step 6: Commit**

```bash
git add tools/scan.py tools/tests/test_scan.py
git commit -m "$(printf 'feat: add read-only archive inventory scanner\n\nMetadata only: os.scandir and os.stat, never a file body, so scanning\n45 GB of cloud-only placeholders downloads nothing. st_blocks > 0\ndistinguishes downloaded files from placeholders. A test asserts no file\nunder the archive is ever opened.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: `tools/dupes.py` — duplicate detection

2,866 redundant copies, 10.1 GB. Catch-all folders mirror siblings exactly, and `2025 Events/archive/` mirrors **2023** events, so sibling lookup must search the whole archive by event name, not within one year.

**Files:**
- Create: `tools/dupes.py`
- Create: `tools/tests/test_dupes.py`

**Interfaces:**
- Consumes: `scan.walk`, `naming.slugify`, `naming.clean_title`
- Produces:
  - `dupes.file_key(row: dict) -> tuple` — `(name.lower(), bytes)`
  - `dupes.group_events(rows: List[dict]) -> Dict[tuple, dict]` — key `(top, year, event, catchall)` → `{"rows", "keys": set, "bytes"}`
  - `dupes.analyze(rows: List[dict]) -> dict` — `{"full": List[dict], "partial": List[dict], "unmatched": List[dict], "removable_files": int, "removable_bytes": int}`
  - `dupes.write_csv(analysis: dict, path: str) -> int` — rows are `rel,verdict,bytes,keeps` where `verdict` is `remove` or `keep-unique`; returns rows written

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_dupes.py
import csv
import os
import shutil
import unittest

from tools import dupes, scan
from tools.tests import fixtures


class TestFileKey(unittest.TestCase):
    def test_name_is_case_insensitive_and_size_matters(self):
        a = {"name": "IMG_0001.JPG", "bytes": 100}
        b = {"name": "img_0001.jpg", "bytes": 100}
        c = {"name": "img_0001.jpg", "bytes": 101}
        self.assertEqual(dupes.file_key(a), dupes.file_key(b))
        self.assertNotEqual(dupes.file_key(a), dupes.file_key(c))


class TestAnalyze(fixtures.ArchiveFixture, unittest.TestCase):
    def rows(self):
        return list(scan.walk(self.archive_root))

    def test_identifies_the_fully_duplicated_catchall_folders(self):
        result = dupes.analyze(self.rows())
        labels = sorted(d["event"] for d in result["full"])
        self.assertIn("1023 Rendr Dinner", labels)
        self.assertIn("0512 Blood Pressure Seminar Flushing", labels)
        self.assertIn("06102023 CAS Award Gala", labels)

    def test_every_removable_file_lives_in_a_catchall(self):
        result = dupes.analyze(self.rows())
        for entry in result["full"]:
            for row in entry["rows"]:
                self.assertTrue(row["catchall"], row["rel"])

    def test_removable_totals_match_the_fixture(self):
        result = dupes.analyze(self.rows())
        self.assertEqual(result["removable_files"], self.archive_stats["dup_files"])
        self.assertEqual(result["removable_bytes"], self.archive_stats["dup_bytes"])

    def test_a_catchall_with_an_extra_file_is_partial_not_full(self):
        extra_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                                 "2022", "1023 Rendr Dinner")
        fixtures.make_seed_image(os.path.join(extra_dir, "UNIQUE_9999.jpg"), "jpg")
        result = dupes.analyze(self.rows())
        partial_events = [p["event"] for p in result["partial"]]
        self.assertIn("1023 Rendr Dinner", partial_events)
        self.assertNotIn("1023 Rendr Dinner", [f["event"] for f in result["full"]])

    def test_partial_overlap_lists_the_unique_file_as_keep(self):
        extra_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                                 "2022", "1023 Rendr Dinner")
        fixtures.make_seed_image(os.path.join(extra_dir, "UNIQUE_9999.jpg"), "jpg")
        result = dupes.analyze(self.rows())
        entry = next(p for p in result["partial"] if p["event"] == "1023 Rendr Dinner")
        unique_names = [r["name"] for r in entry["unique_rows"]]
        self.assertEqual(unique_names, ["UNIQUE_9999.jpg"])

    def test_a_catchall_with_no_sibling_is_unmatched_and_never_removable(self):
        orphan = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                              "2022", "9999 Orphan Event")
        os.makedirs(orphan)
        fixtures.make_seed_image(os.path.join(orphan, "a.jpg"), "jpg")
        result = dupes.analyze(self.rows())
        self.assertIn("9999 Orphan Event", [u["event"] for u in result["unmatched"]])
        removable = [r["rel"] for e in result["full"] for r in e["rows"]]
        self.assertFalse(any("9999 Orphan Event" in r for r in removable))

    def test_cross_year_archive_folder_matches_its_real_year(self):
        # Mirror a 2023 event into 2025's archive/, as the real tree does.
        src = os.path.join(self.archive_root, "Event Photos", "2023 Events",
                           "06102023 CAS Award Gala")
        dst = os.path.join(self.archive_root, "Event Photos", "2025 Events",
                           "archive", "06102023 CAS Award Gala")
        shutil.copytree(src, dst)
        result = dupes.analyze(self.rows())
        matched = [e for e in result["full"]
                   if e["event"] == "06102023 CAS Award Gala"
                   and "2025 Events" in e["rows"][0]["rel"]]
        self.assertTrue(matched, "cross-year archive duplicate not detected")


class TestWriteCsv(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def test_writes_a_verdict_per_file(self):
        result = dupes.analyze(list(scan.walk(self.archive_root)))
        path = os.path.join(self.work, "duplicates.csv")
        written = dupes.write_csv(result, path)
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), written)
        self.assertTrue(all(r["verdict"] in ("remove", "keep-unique") for r in rows))
        self.assertTrue(all(r["keeps"] for r in rows if r["verdict"] == "remove"))
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_dupes -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.dupes'`

- [ ] **Step 3: Implement it**

```python
# tools/dupes.py
"""Find the catch-all folders that duplicate real event folders.

Identity is (filename, size) for every file in the folder. That is strong
enough here: the catch-alls were made by copying, so names and sizes match
exactly, and it costs no reads. A hash would require hydrating 45 GB.

Sibling lookup spans the whole archive, because 2025 Events/archive/ holds
2023 events.
"""
import csv
import os

from tools import naming


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
    originals = {}
    for key, g in groups.items():
        top, year, event, catchall = key
        if catchall:
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
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_dupes -v`
Expected: PASS, 9 tests.

- [ ] **Step 5: Verify the totals against the real archive**

```bash
python3 -c "
from tools import dupes, scan
r='$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos'
a=dupes.analyze(list(scan.walk(r)))
print('full dup folders   ', len(a['full']))
print('partial overlaps   ', len(a['partial']))
print('unmatched          ', len(a['unmatched']))
print('removable          %d files, %.1f GB' % (a['removable_files'], a['removable_bytes']/1024**3))
"
```
Expected: roughly 2,866 removable files and 10.1 GB. The independently measured figure was 2,866 / 10.1 GB — a large gap means the sibling matching is wrong, so inspect `a["unmatched"]` before trusting the result.

- [ ] **Step 6: Commit**

```bash
git add tools/dupes.py tools/tests/test_dupes.py
git commit -m "$(printf 'feat: detect the duplicated catch-all folders\n\nIdentity is (filename, size) per folder, which the copy-made catch-alls\nmatch exactly and which costs no file reads -- hashing would mean\nhydrating 45 GB. Sibling lookup spans the whole archive because\n2025 Events/archive/ actually holds 2023 events.\n\nPartial overlaps are reported file-by-file so nothing unique in\n2024 Events1/ or 2025 Events1/ is ever marked removable.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: `tools/classify.py` — event taxonomy

**Files:**
- Create: `tools/classify.py`
- Create: `tools/tests/test_classify.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `classify.CATEGORIES` — ordered tuple of category ids: `("internal", "opening", "gala", "sponsorship", "seminar", "fair", "cultural", "other")`
  - `classify.LABELS: Dict[str, str]` — id → display name, e.g. `"seminar"` → `"Health Seminars"`
  - `classify.PUBLISHABLE_CATEGORIES` — every id except `"internal"`
  - `classify.category(title: str) -> str`
  - `classify.partners(title: str) -> List[str]` — canonical partner names, sorted
  - `classify.physician(title: str) -> Optional[str]`

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_classify.py
import unittest

from tools import classify


class TestCategory(unittest.TestCase):
    def check(self, title, expected):
        self.assertEqual(classify.category(title), expected, title)

    def test_seminars(self):
        self.check("Dr. Xian Cheung's Diabetes Focus on Diet Seminar with Wellcare & CPC", "seminar")
        self.check("Dr. David Zhuang Health Talk", "seminar")
        self.check("Podiatry Health Seminar at CCBA", "seminar")

    def test_fairs(self):
        self.check("VNS Health Fair & LNY Celebration", "fair")
        self.check("CCPH Wellness Day 2026", "fair")
        self.check("WJ Health Expo", "fair")
        self.check("Spring Into Health & Community Resource Fair", "fair")

    def test_openings(self):
        self.check("Bay ST Grand Opening", "opening")
        self.check("Rendr Flushing Open House with UHC", "opening")
        self.check("Queens Supersite Open House with UHC", "opening")

    def test_galas_and_awards(self):
        self.check("CAS Award Gala", "gala")
        self.check("HCS 26th Anniversary Gala", "gala")
        self.check("Signing Ceremony", "gala")

    def test_sponsorships(self):
        self.check("Breast Cancer Walk", "sponsorship")
        self.check("Swim Across America", "sponsorship")
        self.check("UHC Golf Outing", "sponsorship")

    def test_cultural(self):
        self.check("Chinatown LNY Parade", "cultural")
        self.check("SI 2025 Asian Heritage Celebration", "cultural")
        self.check("CPC Mother & Father's day celebration", "cultural")

    def test_internal_wins_over_everything_else(self):
        # These read like celebrations or dinners but are staff-only.
        self.check("Rendr Dinner", "internal")
        self.check("Team Building Event", "internal")
        self.check("Provider Holiday Party", "internal")
        self.check("PCP End-of-Summer provider dinner", "internal")
        self.check("2025 Physician Shareholder's End-of-Summer Celebration", "internal")
        self.check("End_of _Year Physician celebration 2024", "internal")

    def test_unknown_falls_back_to_other(self):
        self.check("Mystery Folder", "other")

    def test_internal_is_excluded_from_publishable(self):
        self.assertNotIn("internal", classify.PUBLISHABLE_CATEGORIES)
        self.assertIn("seminar", classify.PUBLISHABLE_CATEGORIES)

    def test_every_category_has_a_label(self):
        for cid in classify.CATEGORIES:
            self.assertIn(cid, classify.LABELS)


class TestPartners(unittest.TestCase):
    def test_canonicalizes_payer_aliases(self):
        self.assertEqual(classify.partners("Seminar with UHC & HCS"),
                         ["HCS", "UnitedHealthcare"])
        self.assertEqual(classify.partners("Open House with UnitedHealthcare"),
                         ["UnitedHealthcare"])

    def test_finds_community_partners(self):
        self.assertEqual(
            classify.partners("Dr. Xian Cheung's Diabetes Seminar with Wellcare & CPC"),
            ["CPC", "WellCare"],
        )

    def test_matches_whole_words_only(self):
        # "VNS" must not be found inside an unrelated word.
        self.assertEqual(classify.partners("TRANSVNSPORT event"), [])

    def test_returns_empty_when_no_partner_is_named(self):
        self.assertEqual(classify.partners("Team Building Event"), [])


class TestPhysician(unittest.TestCase):
    def test_finds_dr_prefix(self):
        self.assertEqual(classify.physician("Dr. Harry He Liver Disease Health Seminar"),
                         "Dr. Harry He")

    def test_finds_md_suffix(self):
        self.assertEqual(classify.physician("Hearing and Balance Health Seminar - Kuo Chih Yung, MD"),
                         "Kuo Chih Yung, MD")

    def test_strips_a_possessive(self):
        self.assertEqual(classify.physician("Dr. Brian Poon's Prevention Seminar"),
                         "Dr. Brian Poon")

    def test_returns_none_without_a_physician(self):
        self.assertIsNone(classify.physician("Chinatown LNY Parade"))
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_classify -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.classify'`

- [ ] **Step 3: Implement it**

```python
# tools/classify.py
"""Classify events into the 8 categories used by the gallery.

Order matters. "internal" is tested first because staff events are worded
exactly like public ones -- "Physician Shareholder's End-of-Summer
Celebration" would otherwise land in "cultural". Categories are exclusive;
partners are a separate, cross-cutting field.
"""
import re

CATEGORIES = ("internal", "opening", "gala", "sponsorship", "seminar",
              "fair", "cultural", "other")

LABELS = {
    "internal": "Internal / Provider",
    "opening": "Grand Openings",
    "gala": "Galas & Awards",
    "sponsorship": "Sponsorships & Walks",
    "seminar": "Health Seminars",
    "fair": "Community Health Fairs",
    "cultural": "Cultural & Parades",
    "other": "Other",
}

PUBLISHABLE_CATEGORIES = tuple(c for c in CATEGORIES if c != "internal")

# Keyword sets, tested in CATEGORIES order.
_RULES = {
    "internal": ("team building", "rendr dinner", "holiday party", "provider dinner",
                 "shareholder", "physician celebration", "end-of-summer",
                 "end of summer", "end_of _year", "end of year physician",
                 "staff ", "employee"),
    "opening": ("grand opening", "open house", "ribbon cutting", "supersite open"),
    "gala": ("gala", "anniversary", "award", "ceremony", "banquet"),
    "sponsorship": ("walk", "swim across", "golf", "marathon", "run for", "title sponsor"),
    "seminar": ("seminar", "health talk", "healthtalk", "health education", "lecture"),
    "fair": ("health fair", "wellness", "expo", "resource fair", "community event",
             "flu shot", "screening", "health day", "community day", "wellness day"),
    "cultural": ("lunar new year", "lny", "parade", "heritage", "mother", "father",
                 "birthday", "celebration", "cultural", "easter", "picnic", "festival",
                 "senior center", "senior event", "appreciation"),
}

# Canonical partner name -> aliases matched as whole words.
PARTNERS = {
    "UnitedHealthcare": ("uhc", "unitedhealthcare", "united healthcare"),
    "VNS Health": ("vns", "vns health"),
    "HCS": ("hcs",),
    "Fidelis Care": ("fidelis",),
    "WellCare": ("wellcare",),
    "Healthfirst": ("healthfirst",),
    "Centerlight": ("centerlight",),
    "Anthem BCBS": ("anthem", "bcbs"),
    "VillageCareMax": ("villagecaremax", "villagecare"),
    "CPC": ("cpc", "nan shan"),
    "CCBA": ("ccba",),
    "ACAP": ("acap",),
    "UCA": ("uca", "ucaob"),
    "LiveOnNY": ("liveonny",),
    "CCPH": ("ccph",),
}

# Two name words only. Three would swallow the trailing topic word in
# "Dr. Xian Cheung ACAP Seminar" and "Dr. Harry He Liver Disease".
_PHYSICIAN_DR = re.compile(r"\bDr\.?\s+([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)?)")
_PHYSICIAN_MD = re.compile(r"\b([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3}),\s*MD\b")


def category(title):
    low = title.lower()
    for cid in CATEGORIES:
        if cid == "other":
            continue
        for keyword in _RULES[cid]:
            if keyword in low:
                return cid
    return "other"


def partners(title):
    low = title.lower()
    found = set()
    for canonical, aliases in PARTNERS.items():
        for alias in aliases:
            if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(alias), low):
                found.add(canonical)
                break
    return sorted(found)


def physician(title):
    match = _PHYSICIAN_DR.search(title)
    if match:
        # "Dr. Brian Poon's Prevention..." captures "Brian Poon's".
        words = [re.sub(r"'s$", "", w) for w in match.group(1).split()]
        if words:
            return "Dr. " + " ".join(words[:2])
    match = _PHYSICIAN_MD.search(title)
    if match:
        return "%s, MD" % match.group(1)
    return None
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_classify -v`
Expected: PASS, 18 tests. If a category test fails, the fix is almost always keyword *ordering*, not a missing keyword.

- [ ] **Step 5: Eyeball the real distribution**

```bash
python3 -c "
import collections
from tools import classify, naming, scan
r='$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos'
events={(x['year'],x['event']) for x in scan.walk(r) if x['event'] and x['top']=='Event Photos'}
c=collections.Counter(classify.category(naming.clean_title(e)) for _,e in events)
for k,v in c.most_common(): print('%-14s %d' % (classify.LABELS[k], v))
print()
for y,e in sorted(events)[:12]:
    t=naming.clean_title(e); print('%-10s %-20s %s' % (classify.category(t), classify.partners(t), t[:48]))
"
```
Expected: every category populated and `other` small. If `other` is large, read those titles and extend `_RULES`.

- [ ] **Step 6: Commit**

```bash
git add tools/classify.py tools/tests/test_classify.py
git commit -m "$(printf 'feat: classify events into the 8 gallery categories\n\nRule order is load-bearing: internal staff events are worded like public\nones, so "Physician Shareholder End-of-Summer Celebration" must be tested\nagainst internal before cultural. Partners are cross-cutting rather than\na category, and alias matching is whole-word so VNS is not found inside\nan unrelated string.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: `tools/eventdata.py` + `tools/manifests.py` — the four deliverables

End of Phase B. Produces everything June needs to organize OneDrive herself, plus the picking sheet for Phase C.

**Files:**
- Create: `tools/eventdata.py`
- Create: `tools/manifests.py`
- Create: `tools/tests/test_eventdata.py`
- Create: `tools/tests/test_manifests.py`

**Interfaces:**
- Consumes: `scan.walk`, `scan.write_inventory`, `dupes.analyze`, `dupes.write_csv`, `naming.*`, `classify.*`
- Produces:
  - `eventdata.collect_events(rows: List[dict], extra_dirs=None, tops=("Event Photos",)) -> List[dict]` — one dict per unique event, sorted by `iso` then `title`, each `{"id", "top", "year", "year_num", "event", "title", "iso", "date_pattern", "category", "category_label", "physician", "partners", "photos", "bytes", "hydrated", "catchall", "proposed", "rows", "dir"}`. `id` is `"<iso or year>-<slug>"`, deduplicated with a numeric suffix. `tops` defaults to the events tree only; pass `tops=None` to include the signage folders. `extra_dirs` takes `(rel, top, year, event)` tuples for folders with no files.
  - `eventdata.find_empty_event_dirs(root: str) -> List[tuple]` — `(rel, top, year, event)` for event folders holding no files, to feed `extra_dirs`
  - `eventdata.year_hint(year_folder: str) -> Optional[int]` — `"2022 Events"` → `2022`, `"2026 Event"` → `2026`, `None` when absent
  - `manifests.write_events_manifest(events, dupe_analysis, conflicts, path) -> None`
  - `manifests.write_rename_plan(events, path) -> int`
  - `manifests.write_cleanup(dupe_analysis, archive_root, path, undo_path, stamp) -> int`
  - CLI: `python3 -m tools.manifests --archive PATH [--out tools/out]` — writes all five files and prints a summary

- [ ] **Step 1: Write the failing tests**

```python
# tools/tests/test_eventdata.py
import unittest

from tools import eventdata, scan
from tools.tests import fixtures


class TestYearHint(unittest.TestCase):
    def test_extracts_the_year(self):
        self.assertEqual(eventdata.year_hint("2022 Events"), 2022)
        self.assertEqual(eventdata.year_hint("2026 Event"), 2026)

    def test_none_when_absent(self):
        self.assertIsNone(eventdata.year_hint(None))
        self.assertIsNone(eventdata.year_hint("_Completed Installation Photos"))


class TestCollectEvents(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        # Empty folders hold no files, so they only appear via extra_dirs.
        self.events = eventdata.collect_events(
            list(scan.walk(self.archive_root)),
            extra_dirs=eventdata.find_empty_event_dirs(self.archive_root),
        )

    def by_title(self, needle):
        return next(e for e in self.events if needle in e["title"])

    def test_one_entry_per_unique_event(self):
        titles = [e["title"] for e in self.events]
        self.assertEqual(len(titles), len(set(e["id"] for e in self.events)))

    def test_resolves_dates_using_the_year_folder(self):
        self.assertEqual(self.by_title("Blood Pressure Seminar")["iso"], "2022-05-12")

    def test_carries_category_and_counts(self):
        dinner = self.by_title("Rendr Dinner")
        self.assertEqual(dinner["category"], "internal")
        self.assertEqual(dinner["photos"], 3)
        self.assertGreater(dinner["bytes"], 0)

    def test_extracts_physician_and_partners(self):
        seminar = self.by_title("Xian Cheung")
        self.assertEqual(seminar["physician"], "Dr. Xian Cheung")
        self.assertIn("ACAP", seminar["partners"])

    def test_proposes_an_iso_first_name(self):
        self.assertTrue(self.by_title("CAS Award Gala")["proposed"].startswith("2023-06-10 "))

    def test_includes_empty_event_folders_with_zero_photos(self):
        empty = self.by_title("David Zhuang")
        self.assertEqual(empty["photos"], 0)

    def test_ids_are_unique_and_slug_like(self):
        for e in self.events:
            self.assertRegex(e["id"], r"^[a-z0-9\-]+$")

    def test_sorted_by_date(self):
        dated = [e["iso"] for e in self.events if e["iso"]]
        self.assertEqual(dated, sorted(dated))

    def test_excludes_the_signage_folders_by_default(self):
        tops = {e["top"] for e in self.events}
        self.assertEqual(tops, {"Event Photos"})
        titles = " ".join(e["title"] for e in self.events)
        self.assertNotIn("Chinatown", titles)
        self.assertNotIn("Brooklyn", titles)

    def test_signage_folders_appear_when_tops_is_widened(self):
        rows = list(scan.walk(self.archive_root))
        everything = eventdata.collect_events(rows, tops=None)
        self.assertIn("_Completed Installation Photos",
                      {e["top"] for e in everything})
```

```python
# tools/tests/test_manifests.py
import os
import re
import subprocess
import unittest

from tools import dupes, eventdata, manifests, naming, scan
from tools.tests import fixtures


class TestManifests(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        self.rows = list(scan.walk(self.archive_root))
        self.events = eventdata.collect_events(self.rows)
        self.analysis = dupes.analyze(self.rows)
        self.conflicts = naming.find_conflicts([
            {"name": e["event"], "iso": e["iso"], "path": e["event"]}
            for e in self.events
        ])

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def test_manifest_lists_every_event_and_the_conflicts(self):
        path = os.path.join(self.work, "events-manifest.md")
        manifests.write_events_manifest(self.events, self.analysis, self.conflicts, path)
        with open(path) as fh:
            text = fh.read()
        for e in self.events:
            self.assertIn(e["title"], text)
        self.assertIn("Centerlight", text)
        self.assertIn("needs your decision", text.lower())

    def test_rename_plan_has_a_row_per_event(self):
        path = os.path.join(self.work, "rename-plan.csv")
        count = manifests.write_rename_plan(self.events, path)
        self.assertEqual(count, len(self.events))
        with open(path) as fh:
            header = fh.readline().strip()
        self.assertEqual(header, "current_path,current_name,proposed_name,photos,category")

    def test_cleanup_script_is_executable_quoted_and_safe(self):
        script = os.path.join(self.work, "cleanup.sh")
        undo = os.path.join(self.work, "undo.sh")
        moves = manifests.write_cleanup(
            self.analysis, self.archive_root, script, undo, "2026-10-05")
        self.assertGreater(moves, 0)
        with open(script) as fh:
            text = fh.read()
        self.assertIn("set -euo pipefail", text)
        self.assertNotIn("rm -", text)           # never deletes
        self.assertIn("_DUPLICATES_2026-10-05", text)
        self.assertIn("--apply", text)
        self.assertTrue(os.access(script, os.X_OK))
        # Paths with spaces, parentheses and ampersands must be quoted.
        for line in text.splitlines():
            if line.strip().startswith("mv "):
                self.assertIn("'", line, line)

    def test_cleanup_script_does_nothing_without_apply(self):
        script = os.path.join(self.work, "cleanup.sh")
        manifests.write_cleanup(self.analysis, self.archive_root, script,
                                os.path.join(self.work, "undo.sh"), "2026-10-05")
        before = sorted(f for _, _, fs in os.walk(self.archive_root) for f in fs)
        proc = subprocess.run(["bash", script], capture_output=True, text=True)
        after = sorted(f for _, _, fs in os.walk(self.archive_root) for f in fs)
        self.assertEqual(before, after, "dry run modified the archive")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("dry run", proc.stdout.lower())

    def test_undo_script_reverses_every_move(self):
        script = os.path.join(self.work, "cleanup.sh")
        undo = os.path.join(self.work, "undo.sh")
        manifests.write_cleanup(self.analysis, self.archive_root, script, undo, "2026-10-05")
        before = sorted(
            os.path.relpath(os.path.join(dp, f), self.archive_root)
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        subprocess.run(["bash", script, "--apply"], check=True, capture_output=True)
        moved = sorted(
            os.path.relpath(os.path.join(dp, f), self.archive_root)
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        self.assertNotEqual(before, moved)
        subprocess.run(["bash", undo, "--apply"], check=True, capture_output=True)
        restored = sorted(
            os.path.relpath(os.path.join(dp, f), self.archive_root)
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        self.assertEqual(before, restored)
```

Note: these two tests run the generated script against the **fixture** archive, never the real one. That is the only place any task executes `cleanup.sh`.

- [ ] **Step 2: Run them to make sure they fail**

Run: `python3 -m unittest tools.tests.test_eventdata tools.tests.test_manifests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.eventdata'`

- [ ] **Step 3: Implement `tools/eventdata.py`**

```python
# tools/eventdata.py
"""Aggregate inventory rows into one record per event.

Shared by the manifests (Phase B) and the picker (Phase C) so both describe
events identically.
"""
import os
import re

from tools import classify, naming


def year_hint(year_folder):
    if not year_folder:
        return None
    match = re.search(r"(20\d{2})", year_folder)
    return int(match.group(1)) if match else None


def _event_dirs(rows):
    """Event folders that hold files, keyed (top, year, event, catchall)."""
    groups = {}
    for row in rows:
        if not row["event"]:
            continue
        key = (row["top"], row["year"], row["event"], row["catchall"])
        groups.setdefault(key, []).append(row)
    return groups


def collect_events(rows, extra_dirs=None, tops=("Event Photos",)):
    """One record per event folder.

    `tops` restricts which top-level folders count. It defaults to the events
    tree only: the signage folders are keyed by borough, so leaving them in
    would list "Chinatown" and "Brooklyn" as events.
    """
    if tops:
        rows = [r for r in rows if r["top"] in tops]
    groups = _event_dirs(rows)
    records = []
    for key in groups:
        top, year, event, catchall = key
        group = groups[key]
        hint = year_hint(year)
        parsed = naming.parse_date(event, hint)
        title = naming.clean_title(event)
        records.append({
            "top": top,
            "year": year,
            "year_num": hint,
            "event": event,
            "title": title,
            "iso": parsed["iso"] if parsed else None,
            "date_pattern": parsed["pattern"] if parsed else None,
            "category": classify.category(title),
            "category_label": classify.LABELS[classify.category(title)],
            "physician": classify.physician(title),
            "partners": classify.partners(title),
            "photos": len(group),
            "bytes": sum(r["bytes"] for r in group),
            "hydrated": sum(1 for r in group if r["hydrated"]),
            "catchall": catchall,
            "proposed": naming.proposed_name(event, hint),
            "rows": sorted(group, key=lambda r: r["name"]),
            "dir": os.path.dirname(group[0]["rel"]),
        })

    for folder_rel, top, year, event in (extra_dirs or []):
        hint = year_hint(year)
        parsed = naming.parse_date(event, hint)
        title = naming.clean_title(event)
        records.append({
            "top": top, "year": year, "year_num": hint, "event": event,
            "title": title,
            "iso": parsed["iso"] if parsed else None,
            "date_pattern": parsed["pattern"] if parsed else None,
            "category": classify.category(title),
            "category_label": classify.LABELS[classify.category(title)],
            "physician": classify.physician(title),
            "partners": classify.partners(title),
            "photos": 0, "bytes": 0, "hydrated": 0, "catchall": False,
            "proposed": naming.proposed_name(event, hint),
            "rows": [], "dir": folder_rel,
        })

    records.sort(key=lambda e: (e["iso"] or "9999", e["title"].lower()))
    used = {}
    for record in records:
        base = "%s-%s" % (record["iso"] or (record["year_num"] or "undated"),
                          naming.slugify(record["title"]) or "event")
        base = naming.slugify(base)
        count = used.get(base, 0) + 1
        used[base] = count
        record["id"] = base if count == 1 else "%s-%d" % (base, count)
    return records


def find_empty_event_dirs(root):
    """Event folders containing no files. collect_events() only sees files, so
    empty folders -- which the archive has several of -- need their own pass."""
    found = []
    events_top = os.path.join(root, "Event Photos")
    for dirpath, dirnames, filenames in os.walk(events_top):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        real = [f for f in filenames if not f.startswith(".")]
        if real or dirnames:
            continue
        rel = os.path.relpath(dirpath, root)
        parts = rel.split(os.sep)
        if len(parts) < 3:
            continue
        found.append((rel, parts[0], parts[1], parts[-1]))
    return found
```

- [ ] **Step 4: Implement `tools/manifests.py`**

```python
# tools/manifests.py
"""Write the four organize-it-yourself deliverables plus the picking sheet."""
import argparse
import csv
import os
import shlex
import stat
import sys

from tools import classify, dupes, eventdata, naming, scan

GB = 1024.0 ** 3


def write_events_manifest(events, analysis, conflicts, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lines = []
    lines.append("# Event manifest\n")
    lines.append("Tick the events you want in the portfolio gallery, then run")
    lines.append("`python3 -m tools.hydrate --events <id> <id> ...`\n")
    lines.append("- %d events" % len(events))
    lines.append("- %d duplicate folders (%d files, %.1f GB reclaimable)"
                 % (len(analysis["full"]) + len(analysis["partial"]),
                    analysis["removable_files"], analysis["removable_bytes"] / GB))
    lines.append("")

    if conflicts:
        lines.append("## Needs your decision\n")
        lines.append("The archive gives one event two different dates:\n")
        for c in conflicts:
            lines.append("- **%s** — %s" % (c["title"], " vs ".join(c["dates"])))
            for p in c["paths"]:
                lines.append("  - `%s`" % p)
        lines.append("")

    empties = [e for e in events if e["photos"] == 0]
    if empties:
        lines.append("## Empty folders\n")
        for e in empties:
            lines.append("- `%s`" % e["dir"])
        lines.append("")

    by_category = {}
    for e in events:
        if e["catchall"]:
            continue
        by_category.setdefault(e["category"], []).append(e)

    for cid in classify.CATEGORIES:
        group = by_category.get(cid)
        if not group:
            continue
        note = "  ← not recommended for publication" if cid == "internal" else ""
        lines.append("## %s (%d events)%s\n" % (classify.LABELS[cid], len(group), note))
        lines.append("| pick | date | event | photos | physician | partners | id |")
        lines.append("|---|---|---|---|---|---|---|")
        for e in group:
            lines.append("| [ ] | %s | %s | %d | %s | %s | `%s` |" % (
                e["iso"] or (str(e["year_num"]) if e["year_num"] else "?"),
                e["title"].replace("|", "/"),
                e["photos"],
                e["physician"] or "",
                ", ".join(e["partners"]),
                e["id"],
            ))
        lines.append("")

    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_rename_plan(events, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["current_path", "current_name", "proposed_name",
                         "photos", "category"])
        for e in events:
            writer.writerow([e["dir"], e["event"], e["proposed"],
                             e["photos"], e["category"]])
    return len(events)


_HEADER = """#!/usr/bin/env bash
# Generated by tools/manifests.py on {stamp}. Review before running.
#
# Moves duplicate files into {quarantine}/ inside the archive.
# Nothing is deleted. Re-run undo.sh to reverse every move.
#
#   bash cleanup.sh            # dry run, prints what would move
#   bash cleanup.sh --apply    # actually move
#
# After checking the quarantine folder, delete it from the OneDrive web UI,
# which keeps a 93-day recycle bin.
set -euo pipefail

APPLY=0
[[ "${{1:-}}" == "--apply" ]] && APPLY=1
if [[ $APPLY -eq 0 ]]; then
  echo "DRY RUN -- nothing will move. Re-run with --apply to act."
fi

ARCHIVE={archive}
QUARANTINE="$ARCHIVE/{quarantine}"

move() {{
  local src="$ARCHIVE/$1" dst="$QUARANTINE/$1"
  if [[ ! -e "$src" ]]; then
    echo "skip (already gone): $1"
    return 0
  fi
  if [[ $APPLY -eq 1 ]]; then
    mkdir -p "$(dirname "$dst")"
    mv "$src" "$dst"
  else
    echo "would move: $1"
  fi
}}

"""

_FOOTER = """
if [[ $APPLY -eq 1 ]]; then
  echo "Moved {count} files into $QUARANTINE"
  echo "Reverse with: bash {undo_name} --apply"
else
  echo "{count} files would move. Re-run with --apply."
fi
"""

_UNDO_HEADER = """#!/usr/bin/env bash
# Generated by tools/manifests.py on {stamp}. Reverses cleanup.sh.
set -euo pipefail

APPLY=0
[[ "${{1:-}}" == "--apply" ]] && APPLY=1
if [[ $APPLY -eq 0 ]]; then
  echo "DRY RUN -- nothing will move. Re-run with --apply to act."
fi

ARCHIVE={archive}
QUARANTINE="$ARCHIVE/{quarantine}"

restore() {{
  local src="$QUARANTINE/$1" dst="$ARCHIVE/$1"
  if [[ ! -e "$src" ]]; then
    echo "skip (not quarantined): $1"
    return 0
  fi
  if [[ $APPLY -eq 1 ]]; then
    mkdir -p "$(dirname "$dst")"
    mv "$src" "$dst"
  else
    echo "would restore: $1"
  fi
}}

"""


def _removable(analysis):
    rels = []
    for entry in analysis["full"]:
        rels.extend(r["rel"] for r in entry["rows"])
    for entry in analysis["partial"]:
        rels.extend(r["rel"] for r in entry["dup_rows"])
    return sorted(set(rels))


def _chmod_x(path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_cleanup(analysis, archive_root, path, undo_path, stamp):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    rels = _removable(analysis)
    quarantine = "_DUPLICATES_%s" % stamp
    archive_q = shlex.quote(os.path.abspath(archive_root))

    with open(path, "w") as fh:
        fh.write(_HEADER.format(stamp=stamp, archive=archive_q, quarantine=quarantine))
        for rel in rels:
            fh.write("move %s\n" % shlex.quote(rel))
        fh.write(_FOOTER.format(count=len(rels),
                                undo_name=os.path.basename(undo_path)))
    _chmod_x(path)

    with open(undo_path, "w") as fh:
        fh.write(_UNDO_HEADER.format(stamp=stamp, archive=archive_q,
                                     quarantine=quarantine))
        for rel in rels:
            fh.write("restore %s\n" % shlex.quote(rel))
        fh.write('\necho "done"\n')
    _chmod_x(undo_path)
    return len(rels)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write archive manifests (read-only).")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", default="tools/out")
    ap.add_argument("--stamp", default="2026-10-05")
    args = ap.parse_args(argv)

    out = args.out
    inv_stats = scan.write_inventory(args.archive, os.path.join(out, "inventory.csv"))
    rows = list(scan.walk(args.archive))
    analysis = dupes.analyze(rows)
    dupes.write_csv(analysis, os.path.join(out, "duplicates.csv"))
    events = eventdata.collect_events(
        rows, extra_dirs=eventdata.find_empty_event_dirs(args.archive))
    conflicts = naming.find_conflicts([
        {"name": e["event"], "iso": e["iso"], "path": e["dir"]}
        for e in events if not e["catchall"]
    ])
    write_events_manifest(events, analysis, conflicts,
                          os.path.join(out, "events-manifest.md"))
    write_rename_plan(events, os.path.join(out, "rename-plan.csv"))
    moves = write_cleanup(analysis, args.archive,
                          os.path.join(out, "cleanup.sh"),
                          os.path.join(out, "undo.sh"), args.stamp)

    print("files        %d (%.1f GB)" % (inv_stats["files"], inv_stats["bytes"] / GB))
    print("downloaded   %.1f%%" % (100.0 * inv_stats["hydrated"] / max(inv_stats["files"], 1)))
    print("events       %d" % len([e for e in events if not e["catchall"]]))
    print("duplicates   %d files, %.1f GB" % (analysis["removable_files"],
                                              analysis["removable_bytes"] / GB))
    print("conflicts    %d" % len(conflicts))
    print("cleanup.sh   %d moves queued (dry run by default)" % moves)
    print("\nwrote %s/{inventory.csv,duplicates.csv,events-manifest.md,"
          "rename-plan.csv,cleanup.sh,undo.sh}" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_eventdata tools.tests.test_manifests -v`
Expected: PASS, 17 tests.

- [ ] **Step 6: Run it against the real archive and read the output**

```bash
python3 -m tools.manifests --archive "$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos"
head -60 tools/out/events-manifest.md
```
Expected: ~147 events, ~2,866 duplicate files / ~10.1 GB, and the Centerlight conflict listed under "Needs your decision". **Do not run `tools/out/cleanup.sh`** — that is June's call.

- [ ] **Step 7: Confirm the archive is untouched**

```bash
python3 -c "
from tools import scan
r='$HOME/Library/CloudStorage/OneDrive2-RendrPhysicians/Event_photos'
s=scan.write_inventory(r,'/tmp/recheck.csv'); print(s['files'],'files',s['hydrated'],'downloaded')
"
```
Expected: the same file count as Step 6, and a downloaded count that has only grown by whatever OneDrive synced on its own.

- [ ] **Step 8: Commit**

```bash
git add tools/eventdata.py tools/manifests.py \
        tools/tests/test_eventdata.py tools/tests/test_manifests.py
git commit -m "$(printf 'feat: generate archive manifests and a reversible cleanup script\n\nWrites inventory.csv, duplicates.csv, events-manifest.md, rename-plan.csv\nand a cleanup.sh that June runs herself. The script moves duplicates into\na dated quarantine folder rather than deleting them, defaults to a dry\nrun, quotes every path, and ships with an undo.sh -- tests prove a dry run\nleaves the tree untouched and that undo restores it exactly.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: `tools/hydrate.py` — targeted download

The only module allowed to read file bytes in bulk. Downloads just the picked events: ~25 events ≈ 800 photos ≈ 4 GB, under 9% of the archive.

**Files:**
- Create: `tools/hydrate.py`
- Create: `tools/tests/test_hydrate.py`

**Interfaces:**
- Consumes: `scan.walk`, `eventdata.collect_events`
- Produces:
  - `hydrate.is_hydrated(path: str) -> bool`
  - `hydrate.pull(path: str, chunk: int = 1048576) -> bool` — reads the file through to force materialization; `True` on success
  - `hydrate.run(archive: str, event_ids: List[str], progress=None) -> dict` — `{"events", "files", "already", "pulled", "failed", "bytes"}`
  - CLI: `python3 -m tools.hydrate --archive PATH --events ID [ID ...]`, plus `--manifest tools/out/events-manifest.md` to read ticked `[x]` rows instead

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_hydrate.py
import os
import unittest

from tools import eventdata, hydrate, scan
from tools.tests import fixtures


class TestHydrate(fixtures.ArchiveFixture, unittest.TestCase):
    def ids_for(self, needle):
        events = eventdata.collect_events(list(scan.walk(self.archive_root)))
        return [e["id"] for e in events if needle in e["title"]]

    def test_local_fixture_files_report_as_hydrated(self):
        path = next(r["path"] for r in scan.walk(self.archive_root))
        self.assertTrue(hydrate.is_hydrated(path))

    def test_pull_reads_a_file_successfully(self):
        path = next(r["path"] for r in scan.walk(self.archive_root))
        self.assertTrue(hydrate.pull(path))

    def test_pull_reports_failure_for_a_missing_file(self):
        self.assertFalse(hydrate.pull(os.path.join(self.archive_root, "nope.jpg")))

    def test_run_touches_only_the_requested_events(self):
        target = self.ids_for("Rendr Dinner")
        seen = []
        result = hydrate.run(self.archive_root, target,
                             progress=lambda row: seen.append(row["rel"]))
        self.assertEqual(result["events"], 1)
        self.assertEqual(result["files"], 3)   # fixture plants 3 photos
        self.assertTrue(all("Rendr Dinner" in rel for rel in seen))

    def test_run_skips_files_already_present(self):
        target = self.ids_for("Rendr Dinner")
        result = hydrate.run(self.archive_root, target)
        self.assertEqual(result["already"], 3)
        self.assertEqual(result["pulled"], 0)

    def test_run_ignores_unknown_ids(self):
        result = hydrate.run(self.archive_root, ["no-such-event-id"])
        self.assertEqual(result["events"], 0)
        self.assertEqual(result["files"], 0)

    def test_run_never_writes_to_the_archive(self):
        before = sorted(
            (os.path.relpath(os.path.join(dp, f), self.archive_root),
             os.path.getsize(os.path.join(dp, f)))
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        hydrate.run(self.archive_root, self.ids_for("Rendr Dinner"))
        after = sorted(
            (os.path.relpath(os.path.join(dp, f), self.archive_root),
             os.path.getsize(os.path.join(dp, f)))
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        self.assertEqual(before, after)


class TestManifestParsing(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()
        self.path = os.path.join(self.tmp, "events-manifest.md")
        with open(self.path, "w") as fh:
            fh.write(
                "| pick | date | event | photos | physician | partners | id |\n"
                "|---|---|---|---|---|---|---|\n"
                "| [x] | 2026-06-09 | Diabetes | 11 |  |  | `2026-06-09-diabetes` |\n"
                "| [ ] | 2026-03-01 | Parade | 4 |  |  | `2026-03-01-parade` |\n"
                "| [X] | 2025-05-08 | Opening | 27 |  |  | `2025-05-08-opening` |\n"
            )

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_reads_only_ticked_rows_case_insensitively(self):
        self.assertEqual(
            hydrate.ids_from_manifest(self.path),
            ["2026-06-09-diabetes", "2025-05-08-opening"],
        )
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_hydrate -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.hydrate'`

- [ ] **Step 3: Implement it**

```python
# tools/hydrate.py
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
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_hydrate -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/hydrate.py tools/tests/test_hydrate.py
git commit -m "$(printf 'feat: download only the selected events\n\nReading a placeholder is what makes macOS File Provider materialize it,\nso pull() reads each file through. Confined to the picked events: about\n25 events is roughly 800 photos and 4 GB, under 9%% of the archive.\nAlready-downloaded files are skipped and failures are retryable.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 12: `tools/thumbs.py` — thumbnails and the local picker

**Files:**
- Create: `tools/thumbs.py`
- Create: `tools/picker/picker.css`, `tools/picker/picker.js`
- Create: `tools/tests/test_thumbs.py`

**Interfaces:**
- Consumes: `eventdata.collect_events`, `images.thumb`, `images.SipsError`, `classify.LABELS`
- Produces:
  - `thumbs.build(archive: str, event_ids: List[str], thumb_dir: str, html_path: str) -> dict` — `{"events": int, "thumbs": int, "skipped": List[dict]}`
  - `thumbs.render_html(events: List[dict]) -> str` — the picker page; internal events render with a `<details>` wrapper that is closed by default
  - CLI: `python3 -m tools.thumbs --archive PATH --events ID [ID ...] | --manifest PATH`

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_thumbs.py
import json
import os
import unittest

from tools import eventdata, scan, thumbs
from tools.tests import fixtures


class TestThumbs(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        self.thumb_dir = os.path.join(self.work, "thumbs")
        self.html = os.path.join(self.work, "index.html")
        self.events = eventdata.collect_events(list(scan.walk(self.archive_root)))

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def ids_for(self, *needles):
        return [e["id"] for e in self.events
                if any(n in e["title"] for n in needles)]

    def test_writes_one_thumbnail_per_photo(self):
        ids = self.ids_for("Rendr Dinner")
        result = thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        self.assertEqual(result["thumbs"], 3)
        self.assertEqual(len(os.listdir(self.thumb_dir)), 3)

    def test_thumbnails_are_small_jpegs(self):
        ids = self.ids_for("Rendr Dinner")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        for name in os.listdir(self.thumb_dir):
            path = os.path.join(self.thumb_dir, name)
            self.assertTrue(name.endswith(".jpg"))
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(2), b"\xff\xd8")

    def test_converts_heic_sources(self):
        ids = self.ids_for("Centerlight")
        result = thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        self.assertGreater(result["thumbs"], 0)
        self.assertEqual(result["skipped"], [])

    def test_html_embeds_absolute_source_paths_for_full_size_viewing(self):
        ids = self.ids_for("Rendr Dinner")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        with open(self.html) as fh:
            text = fh.read()
        self.assertIn(self.archive_root, text)

    def test_internal_events_are_collapsed_and_flagged(self):
        ids = self.ids_for("Rendr Dinner", "Blood Pressure Seminar")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        with open(self.html) as fh:
            text = fh.read()
        self.assertIn("<details", text)
        self.assertNotIn("<details open", text)
        self.assertIn("Internal / Provider", text)

    def test_html_carries_a_json_payload_the_picker_can_read(self):
        ids = self.ids_for("Rendr Dinner")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        with open(self.html) as fh:
            text = fh.read()
        start = text.index('id="picker-data"')
        payload = text[text.index(">", start) + 1:text.index("</script>", start)]
        data = json.loads(payload)
        self.assertEqual(len(data["events"]), 1)
        self.assertIn("rel", data["events"][0]["photos"][0])

    def test_reports_unreadable_sources_instead_of_crashing(self):
        bad_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                               "9999 Broken Event")
        os.makedirs(bad_dir)
        with open(os.path.join(bad_dir, "broken.jpg"), "w") as fh:
            fh.write("not an image")
        events = eventdata.collect_events(list(scan.walk(self.archive_root)))
        ids = [e["id"] for e in events if "Broken Event" in e["title"]]
        result = thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        self.assertEqual(result["thumbs"], 0)
        self.assertEqual(len(result["skipped"]), 1)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_thumbs -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.thumbs'`

- [ ] **Step 3: Implement `tools/thumbs.py`**

```python
# tools/thumbs.py
"""Generate thumbnails and the local picker page.

The picker is local only: it points at absolute archive paths so clicking a
thumbnail opens the full original, which is how faces get checked before
anything is published. It is never committed and never deployed.
"""
import argparse
import html
import json
import os
import sys

from tools import classify, eventdata, hydrate, images, scan


def _thumb_name(event_id, index):
    return "%s-%03d.jpg" % (event_id, index)


def build(archive, event_ids, thumb_dir, html_path):
    wanted = set(event_ids)
    events = eventdata.collect_events(list(scan.walk(archive)))
    chosen = [e for e in events if e["id"] in wanted]
    os.makedirs(thumb_dir, exist_ok=True)

    payload = []
    made = 0
    skipped = []
    for event in chosen:
        photos = []
        for i, row in enumerate(event["rows"], start=1):
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
    data = json.dumps({"events": events}, indent=1)
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
<script type="application/json" id="picker-data">
%s
</script>
<script src="picker.js"></script>
</body>
</html>
""" % (filters, "\n".join(groups), data)


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
```

- [ ] **Step 4: Write the picker's stylesheet and script**

`tools/picker/picker.css`:

```css
:root { --line:#dbe5e2; --accent:#075c57; --muted:#5d6b69; color-scheme: light dark; }
* { box-sizing: border-box; }
body { font: 15px/1.5 system-ui, -apple-system, sans-serif; margin: 0; padding: 1rem 1.25rem 4rem; }
header { position: sticky; top: 0; background: Canvas; padding: .75rem 0; border-bottom: 1px solid var(--line); z-index: 5; }
h1 { font-size: 1.1rem; margin: 0 0 .25rem; }
.count { margin: .25rem 0; font-weight: 600; }
.hint { color: var(--muted); font-size: .85rem; max-width: 60ch; }
.filters { display: flex; flex-wrap: wrap; gap: .35rem; margin: .5rem 0; }
.filter, .export { border: 1px solid var(--line); background: transparent; border-radius: 999px; padding: .3rem .7rem; cursor: pointer; font: inherit; }
.filter[aria-pressed="true"] { background: var(--accent); color: white; border-color: var(--accent); }
.export { border-color: var(--accent); color: var(--accent); font-weight: 600; }
.event { margin: 1.5rem 0; }
.event h2 { font-size: 1rem; margin: 0 0 .5rem; }
.meta { color: var(--muted); font-weight: 400; font-size: .85rem; }
.event[hidden], .internal[hidden] { display: none; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: .6rem; }
.tile { position: relative; display: block; }
.tile img { width: 100%; aspect-ratio: 4/3; object-fit: cover; border-radius: 10px; border: 3px solid transparent; cursor: zoom-in; display: block; }
.tile input[type="checkbox"] { position: absolute; top: .4rem; left: .4rem; width: 1.25rem; height: 1.25rem; z-index: 2; }
.tile input[type="checkbox"]:checked ~ img { border-color: var(--accent); }
.cap { width: 100%; margin-top: .25rem; font: inherit; font-size: .8rem; padding: .2rem .35rem; border: 1px solid var(--line); border-radius: 6px; background: transparent; color: inherit; }
summary { cursor: pointer; font-weight: 600; padding: .5rem 0; }
.internal { border-left: 3px solid #c47b1a; padding-left: .75rem; }
```

`tools/picker/picker.js`:

```javascript
// Local picker. Selections live in localStorage so picking can span sittings.
const KEY = "june-picker-v1";
const state = load();

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || { picks: {}, caps: {} }; }
  catch { return { picks: {}, caps: {} }; }
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {}
}
function count() {
  return Object.values(state.picks).filter(Boolean).length;
}
function paintCount() {
  document.querySelector("[data-count]").textContent = String(count());
}

// Restore previous session
document.querySelectorAll("[data-pick]").forEach((box) => {
  box.checked = Boolean(state.picks[box.dataset.pick]);
  box.addEventListener("change", () => {
    state.picks[box.dataset.pick] = box.checked;
    save();
    paintCount();
  });
});
document.querySelectorAll("[data-cap]").forEach((input) => {
  if (state.caps[input.dataset.cap]) input.value = state.caps[input.dataset.cap];
  input.addEventListener("input", () => {
    state.caps[input.dataset.cap] = input.value;
    save();
  });
});

// Click the image (not the checkbox) to open the full-size original
document.querySelectorAll(".tile img").forEach((img) => {
  img.addEventListener("click", (e) => {
    e.preventDefault();
    window.open("file://" + encodeURI(img.dataset.full), "_blank");
  });
});

// Category filters
const groups = [...document.querySelectorAll(".event")];
document.querySelectorAll(".filter").forEach((btn) => {
  btn.addEventListener("click", () => {
    const want = btn.dataset.filter;
    document.querySelectorAll(".filter").forEach((b) =>
      b.setAttribute("aria-pressed", String(b === btn))
    );
    groups.forEach((g) => {
      g.hidden = want !== "all" && g.dataset.category !== want;
    });
  });
});

// Export
document.querySelector("[data-export]").addEventListener("click", () => {
  const payload = { photos: [] };
  for (const [key, on] of Object.entries(state.picks)) {
    if (!on) continue;
    const [eventId, rel] = key.split("|");
    payload.photos.push({
      event_id: eventId,
      rel,
      caption: state.caps[key] || "",
    });
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "selection.json";
  a.click();
  URL.revokeObjectURL(a.href);
});

paintCount();
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_thumbs -v`
Expected: PASS, 7 tests.

- [ ] **Step 6: Commit**

```bash
git add tools/thumbs.py tools/picker/picker.css tools/picker/picker.js \
        tools/tests/test_thumbs.py
git commit -m "$(printf 'feat: add thumbnail generation and the local photo picker\n\nThe picker links each thumbnail to the absolute path of its original so\nfaces can be checked at full size before anything is published. Internal\nprovider events render inside a closed <details> and are labeled as not\nrecommended, per the privacy decision: shown, not hidden, not preselected.\n\nSelections and captions persist in localStorage so picking can span\nseveral sittings. Unreadable sources are reported, not fatal.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 13: `tools/build_assets.py` — selection to published assets

**Files:**
- Create: `tools/build_assets.py`
- Create: `tools/tests/test_build_assets.py`

**Interfaces:**
- Consumes: `eventdata.collect_events`, `images.web`, `images.thumb`, `scan.walk`
- Produces:
  - `build_assets.build(archive, selection_path, assets_dir, data_path, featured=8, json_path=None) -> dict` — `{"events", "photos", "bytes", "skipped", "data"}`. `json_path` is opt-in so tests do not write into the repo.
  - `build_assets.render_data_js(data: dict) -> str` — `"window.GALLERY_DATA = {...};\n"`
  - Written files: `assets/events/<event_id>-NNN.jpg`, `assets/events/thumbs/<event_id>-NNN.jpg`, `data/events.js`, `tools/out/events.json`
  - CLI: `python3 -m tools.build_assets --archive PATH --selection selection.json`

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_build_assets.py
import json
import os
import re
import unittest

from tools import build_assets, eventdata, scan
from tools.tests import fixtures


class TestBuildAssets(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        self.assets = os.path.join(self.work, "assets", "events")
        self.data = os.path.join(self.work, "data", "events.js")
        self.events = eventdata.collect_events(list(scan.walk(self.archive_root)))
        self.selection = os.path.join(self.work, "selection.json")

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def write_selection(self, needle, captions=True):
        event = next(e for e in self.events if needle in e["title"])
        photos = [{"event_id": event["id"], "rel": r["rel"],
                   "caption": "Caption %d" % i if captions else ""}
                  for i, r in enumerate(event["rows"], start=1)]
        with open(self.selection, "w") as fh:
            json.dump({"photos": photos}, fh)
        return event

    def build(self):
        return build_assets.build(self.archive_root, self.selection,
                                  self.assets, self.data, featured=2)

    def test_publishes_a_web_image_and_a_thumbnail_per_photo(self):
        event = self.write_selection("Rendr Dinner")
        result = self.build()
        self.assertEqual(result["photos"], 3)
        self.assertEqual(len(os.listdir(self.assets)) - 1, 3)   # minus thumbs/
        self.assertEqual(len(os.listdir(os.path.join(self.assets, "thumbs"))), 3)

    def test_writes_a_loadable_js_data_file(self):
        self.write_selection("Rendr Dinner")
        self.build()
        with open(self.data) as fh:
            text = fh.read()
        self.assertTrue(text.startswith("window.GALLERY_DATA = "))
        self.assertTrue(text.rstrip().endswith(";"))
        payload = json.loads(text[len("window.GALLERY_DATA = "):].rstrip().rstrip(";"))
        self.assertEqual(len(payload["events"]), 1)

    def test_records_real_pixel_dimensions(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        photo = result["data"]["events"][0]["photos"][0]
        self.assertGreater(photo["w"], 0)
        self.assertGreater(photo["h"], 0)

    def test_paths_are_repo_relative_and_forward_slashed(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        photo = result["data"]["events"][0]["photos"][0]
        self.assertTrue(photo["src"].startswith("assets/events/"))
        self.assertTrue(photo["thumb"].startswith("assets/events/thumbs/"))
        self.assertNotIn("\\", photo["src"])

    def test_keeps_the_caption_from_the_selection(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        self.assertEqual(result["data"]["events"][0]["photos"][0]["caption"],
                         "Caption 1")

    def test_falls_back_to_the_event_title_when_caption_is_blank(self):
        event = self.write_selection("Rendr Dinner", captions=False)
        result = self.build()
        self.assertEqual(result["data"]["events"][0]["photos"][0]["caption"],
                         event["title"])

    def test_carries_event_metadata_into_the_payload(self):
        self.write_selection("Blood Pressure Seminar")
        result = self.build()
        event = result["data"]["events"][0]
        for key in ("id", "date", "title", "category", "category_label",
                    "physician", "partners", "featured", "photos"):
            self.assertIn(key, event)

    def test_marks_only_the_first_n_photos_as_featured(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        featured = [p for e in result["data"]["events"] for p in e["photos"]
                    if p["featured"]]
        self.assertEqual(len(featured), 2)   # featured=2

    def test_converts_heic_selections_to_jpeg(self):
        self.write_selection("Centerlight")
        result = self.build()
        self.assertEqual(result["skipped"], [])
        for name in os.listdir(self.assets):
            if name == "thumbs":
                continue
            self.assertTrue(name.endswith(".jpg"))

    def test_every_published_file_stays_under_the_size_cap(self):
        self.write_selection("Rendr Dinner")
        self.build()
        for root, dirs, files in os.walk(self.assets):
            for name in files:
                self.assertLess(os.path.getsize(os.path.join(root, name)), 500 * 1024)

    def test_ignores_selection_entries_whose_event_is_unknown(self):
        with open(self.selection, "w") as fh:
            json.dump({"photos": [{"event_id": "nope", "rel": "x.jpg", "caption": ""}]}, fh)
        result = self.build()
        self.assertEqual(result["photos"], 0)
        self.assertEqual(len(result["skipped"]), 1)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_build_assets -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.build_assets'`

- [ ] **Step 3: Implement it**

```python
# tools/build_assets.py
"""Turn selection.json into published assets plus data/events.js.

Data ships as JavaScript rather than JSON because fetch() is blocked on
file:// URLs, and the site must work when index.html is opened directly.
A JSON copy goes to tools/out/events.json for tooling and review.
"""
import argparse
import json
import os
import sys

from tools import eventdata, images, scan


def _rel_posix(*parts):
    return "/".join(parts)


def build(archive, selection_path, assets_dir, data_path, featured=8,
          json_path=None):
    """json_path is optional: a cwd-relative default would make the tests
    write into the real repo."""
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
    os.makedirs(thumbs_dir, exist_ok=True)

    out_events = []
    total_photos = 0
    total_bytes = 0
    featured_left = featured

    for event_id in sorted(picked, key=lambda i: (events[i]["iso"] or "9999", i)):
        event = events[event_id]
        photos = []
        for index, (item, row) in enumerate(picked[event_id], start=1):
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
    os.makedirs(os.path.dirname(data_path) or ".", exist_ok=True)
    with open(data_path, "w") as fh:
        fh.write(render_data_js(data))

    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
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
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_build_assets -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/build_assets.py tools/tests/test_build_assets.py
git commit -m "$(printf 'feat: publish selected photos and generate gallery data\n\nEmits 1400px web JPEGs, 480px thumbnails, and data/events.js. Data ships\nas JavaScript, not JSON, because fetch() is blocked on file:// and the\nREADME promises the site works by opening index.html directly. A JSON\ncopy still goes to tools/out/events.json for review.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 14: `events.html` — the public gallery

**Files:**
- Create: `events.html`
- Create: `gallery.css`
- Create: `gallery.js`
- Create: `tools/tests/js/gallery.test.js`
- Modify: `index.html` (nav gains an Events link)

**Interfaces:**
- Consumes: `window.GALLERY_DATA` from `data/events.js`
- Produces: `window.Gallery = { filterEvents, yearsOf, categoriesOf, flattenPhotos, init }` — pure functions, which is what the Node tests exercise

- [ ] **Step 1: Write the failing JS test**

```javascript
// tools/tests/js/gallery.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// gallery.js is a classic script so it works on file://. Load it into a
// sandbox with a stub DOM and pull the pure functions off window.Gallery.
function load() {
  const sandbox = {
    window: {},
    document: {
      addEventListener() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => ({ style: {}, classList: { add() {}, toggle() {} },
                              setAttribute() {}, append() {}, addEventListener() {} }),
    },
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(readFileSync("gallery.js", "utf8"), sandbox);
  return sandbox.window.Gallery;
}

const EVENTS = [
  { id: "a", date: "2026-06-09", year: "2026", title: "Diabetes", category: "seminar",
    photos: [{ src: "1.jpg", featured: true }, { src: "2.jpg", featured: false }] },
  { id: "b", date: "2025-05-08", year: "2025", title: "Opening", category: "opening",
    photos: [{ src: "3.jpg", featured: true }] },
  { id: "c", date: "2026-03-01", year: "2026", title: "Parade", category: "cultural",
    photos: [{ src: "4.jpg", featured: false }] },
];

test("filterEvents returns everything for the all/all case", () => {
  const G = load();
  assert.equal(G.filterEvents(EVENTS, { year: "all", category: "all" }).length, 3);
});

test("filterEvents narrows by year", () => {
  const G = load();
  const got = G.filterEvents(EVENTS, { year: "2026", category: "all" });
  assert.deepEqual(got.map((e) => e.id), ["a", "c"]);
});

test("filterEvents narrows by category", () => {
  const G = load();
  const got = G.filterEvents(EVENTS, { year: "all", category: "opening" });
  assert.deepEqual(got.map((e) => e.id), ["b"]);
});

test("filterEvents combines both filters", () => {
  const G = load();
  assert.equal(G.filterEvents(EVENTS, { year: "2025", category: "cultural" }).length, 0);
});

test("filterEvents tolerates missing options", () => {
  const G = load();
  assert.equal(G.filterEvents(EVENTS, {}).length, 3);
});

test("yearsOf returns newest first without duplicates", () => {
  const G = load();
  assert.deepEqual(G.yearsOf(EVENTS), ["2026", "2025"]);
});

test("categoriesOf returns the categories present, sorted", () => {
  const G = load();
  assert.deepEqual(G.categoriesOf(EVENTS), ["cultural", "opening", "seminar"]);
});

test("flattenPhotos pairs each photo with its event", () => {
  const G = load();
  const flat = G.flattenPhotos(EVENTS);
  assert.equal(flat.length, 4);
  assert.equal(flat[0].event.id, "a");
  assert.equal(flat[0].photo.src, "1.jpg");
});

test("flattenPhotos can return only featured photos", () => {
  const G = load();
  assert.equal(G.flattenPhotos(EVENTS, { featuredOnly: true }).length, 2);
});

test("loading gallery.js without a gallery container does not throw", () => {
  assert.doesNotThrow(() => load());
});
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `export PATH="$HOME/.local/bin:$PATH" && node --test tools/tests/js/`
Expected: FAIL — `ENOENT: no such file or directory, open 'gallery.js'`

- [ ] **Step 3: Write `gallery.js`**

```javascript
// Gallery: pure data helpers plus a DOM renderer.
// Classic script (not a module) so it works from file:// as well as HTTP.
(function () {
  const Gallery = {};

  Gallery.filterEvents = function (events, opts) {
    const o = opts || {};
    const year = o.year || "all";
    const category = o.category || "all";
    return events.filter(
      (e) =>
        (year === "all" || e.year === year) &&
        (category === "all" || e.category === category)
    );
  };

  Gallery.yearsOf = function (events) {
    return [...new Set(events.map((e) => e.year).filter(Boolean))].sort().reverse();
  };

  Gallery.categoriesOf = function (events) {
    return [...new Set(events.map((e) => e.category).filter(Boolean))].sort();
  };

  Gallery.flattenPhotos = function (events, opts) {
    const featuredOnly = Boolean(opts && opts.featuredOnly);
    const out = [];
    events.forEach((event) =>
      (event.photos || []).forEach((photo) => {
        if (featuredOnly && !photo.featured) return;
        out.push({ event, photo });
      })
    );
    return out;
  };

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderGrid(host, events, lightbox) {
    host.textContent = "";
    const flat = Gallery.flattenPhotos(events);
    if (flat.length === 0) {
      host.append(el("p", "gal-empty", "No events match these filters."));
      return;
    }
    flat.forEach(({ event, photo }, i) => {
      const fig = el("figure", "gal-item");
      const img = document.createElement("img");
      img.src = photo.thumb || photo.src;
      img.width = photo.w || 0;
      img.height = photo.h || 0;
      img.loading = "lazy";
      img.decoding = "async";
      img.alt = photo.caption || event.title;
      img.addEventListener("click", () => lightbox.open(flat, i));
      const cap = el("figcaption");
      cap.append(el("span", "gal-title", event.title));
      cap.append(el("span", "gal-meta",
        [event.date, event.category_label].filter(Boolean).join(" · ")));
      fig.append(img, cap);
      host.append(fig);
    });
  }

  function makeLightbox() {
    const box = el("div", "gal-lightbox");
    box.hidden = true;
    const img = document.createElement("img");
    const cap = el("p", "gal-lightbox-cap");
    const close = el("button", "gal-close", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    const prev = el("button", "gal-arrow gal-arrow-prev", "◀");
    const next = el("button", "gal-arrow gal-arrow-next", "▶");
    prev.type = next.type = "button";
    prev.setAttribute("aria-label", "Previous photo");
    next.setAttribute("aria-label", "Next photo");
    box.append(close, prev, img, next, cap);
    document.body.append(box);

    let items = [];
    let at = 0;
    const show = (i) => {
      at = (i + items.length) % items.length;
      const { event, photo } = items[at];
      img.src = photo.src;
      img.alt = photo.caption || event.title;
      cap.textContent = [event.title, event.date, photo.caption]
        .filter(Boolean).join(" · ");
    };
    const hide = () => { box.hidden = true; document.body.style.overflow = ""; };

    close.addEventListener("click", hide);
    prev.addEventListener("click", () => show(at - 1));
    next.addEventListener("click", () => show(at + 1));
    box.addEventListener("click", (e) => { if (e.target === box) hide(); });
    document.addEventListener("keydown", (e) => {
      if (box.hidden) return;
      if (e.key === "Escape") hide();
      if (e.key === "ArrowLeft") show(at - 1);
      if (e.key === "ArrowRight") show(at + 1);
    });

    return {
      open(list, i) {
        items = list;
        box.hidden = false;
        document.body.style.overflow = "hidden";
        show(i);
      },
    };
  }

  function chip(label, value, group, onPick) {
    const btn = el("button", "gal-chip", label);
    btn.type = "button";
    btn.dataset.value = value;
    btn.dataset.group = group;
    btn.addEventListener("click", () => onPick(group, value, btn));
    return btn;
  }

  Gallery.init = function () {
    const host = document.querySelector("[data-gallery]");
    if (!host) return;
    const data = window.GALLERY_DATA;
    const events = (data && data.events) || [];
    const grid = host.querySelector("[data-gallery-grid]");
    const yearBar = host.querySelector("[data-gallery-years]");
    const catBar = host.querySelector("[data-gallery-categories]");
    const countEl = host.querySelector("[data-gallery-count]");
    if (!grid) return;

    if (events.length === 0) {
      grid.append(el("p", "gal-empty",
        "Gallery data has not been built yet. Run tools/build_assets.py."));
      return;
    }

    const lightbox = makeLightbox();
    const picked = { year: "all", category: "all" };

    const paint = () => {
      const shown = Gallery.filterEvents(events, picked);
      renderGrid(grid, shown, lightbox);
      if (countEl) {
        const photos = Gallery.flattenPhotos(shown).length;
        countEl.textContent = `${shown.length} events · ${photos} photos`;
      }
    };

    const onPick = (group, value, btn) => {
      picked[group] = value;
      const bar = group === "year" ? yearBar : catBar;
      if (bar) {
        [...bar.children].forEach((b) =>
          b.setAttribute("aria-pressed", String(b === btn))
        );
      }
      paint();
    };

    if (yearBar) {
      const all = chip("All years", "all", "year", onPick);
      all.setAttribute("aria-pressed", "true");
      yearBar.append(all);
      Gallery.yearsOf(events).forEach((y) =>
        yearBar.append(chip(y, y, "year", onPick))
      );
    }
    if (catBar) {
      const all = chip("All types", "all", "category", onPick);
      all.setAttribute("aria-pressed", "true");
      catBar.append(all);
      Gallery.categoriesOf(events).forEach((c) => {
        const label = (events.find((e) => e.category === c) || {}).category_label || c;
        catBar.append(chip(label, c, "category", onPick));
      });
    }
    paint();
  };

  window.Gallery = Gallery;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", Gallery.init);
  } else {
    Gallery.init();
  }
})();
```

- [ ] **Step 4: Run the JS tests and make sure they pass**

Run: `export PATH="$HOME/.local/bin:$PATH" && node --test tools/tests/js/`
Expected: PASS, 10 tests.

- [ ] **Step 5: Write `gallery.css`**

```css
/* Gallery page. Tokens come from style.css, which loads first. */
.gal-head { margin-bottom: 1.25rem; }
.gal-filters { display: flex; flex-direction: column; gap: .5rem; margin: 1rem 0; }
.gal-bar { display: flex; flex-wrap: wrap; gap: .4rem; }
.gal-chip { font: inherit; font-size: .85rem; padding: .35rem .8rem; border: 1px solid var(--line); border-radius: 999px; background: transparent; color: var(--text); cursor: pointer; }
.gal-chip:hover { border-color: var(--accent); color: var(--accent); }
.gal-chip[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
.gal-chip:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.gal-count { color: var(--muted); font-size: .85rem; margin: .5rem 0 1rem; }
.gal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 1rem; }
.gal-item { margin: 0; }
.gal-item img { width: 100%; height: auto; aspect-ratio: 4 / 3; object-fit: cover; border-radius: 14px; border: 1px solid var(--line); background: var(--tint); cursor: zoom-in; display: block; }
.gal-item figcaption { display: flex; flex-direction: column; gap: .1rem; margin-top: .45rem; }
.gal-title { font-weight: 600; font-size: .9rem; }
.gal-meta { color: var(--muted); font-size: .8rem; }
.gal-empty { color: var(--muted); grid-column: 1 / -1; }

.gal-lightbox { position: fixed; inset: 0; z-index: 50; background: rgba(8, 14, 13, .92); display: grid; place-items: center; padding: 3rem 1rem; }
.gal-lightbox[hidden] { display: none; }
.gal-lightbox img { max-width: min(100%, 1200px); max-height: 80vh; border-radius: 10px; }
.gal-lightbox-cap { color: #e9f0ee; text-align: center; margin: .75rem 0 0; font-size: .9rem; max-width: 70ch; }
.gal-close { position: absolute; top: 1rem; right: 1rem; }
.gal-close, .gal-arrow { font: inherit; background: rgba(255, 255, 255, .12); color: #fff; border: 0; border-radius: 999px; width: 2.5rem; height: 2.5rem; cursor: pointer; }
.gal-close:hover, .gal-arrow:hover { background: rgba(255, 255, 255, .25); }
.gal-arrow-prev { position: absolute; left: 1rem; }
.gal-arrow-next { position: absolute; right: 1rem; }

@media (max-width: 720px) {
  .gal-grid { grid-template-columns: 1fr 1fr; gap: .6rem; }
  .gal-lightbox { padding: 4rem .5rem; }
  .gal-arrow-prev { left: .25rem; }
  .gal-arrow-next { right: .25rem; }
}
```

- [ ] **Step 6: Write `events.html`**

The nav must carry `#year`, `.theme-toggle`, `.nav-toggle` and `.nav-links`, or the guards added in Task 5 silently disable the theme toggle and menu:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Event Gallery — Hui Jun (June) Wen</title>
  <meta name="description" content="Community health seminars, health fairs, clinic grand openings and payer partnership events led by Hui Jun (June) Wen in New York City.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="gallery.css">
</head>
<body>
  <header class="nav">
    <a class="brand" href="index.html">Hui Jun Wen</a>
    <button class="nav-toggle" aria-label="Open menu" aria-expanded="false">☰</button>
    <nav class="nav-links">
      <a href="index.html#work">Work</a>
      <a href="index.html#seminars">Seminars</a>
      <a href="events.html" aria-current="page">Events</a>
      <a href="index.html#experience">Experience</a>
      <a href="index.html#contact">Contact</a>
      <button class="theme-toggle" aria-label="Toggle dark mode">◐</button>
    </nav>
  </header>

  <main id="top">
    <section class="section" data-gallery>
      <div class="wrap">
        <div class="gal-head">
          <p class="eyebrow">Event gallery</p>
          <h2>Community programs, as they happened.</h2>
          <p class="lead">Physician-led seminars, health fairs, clinic launches and payer partnership events across Brooklyn, Queens, Manhattan and Staten Island.</p>
        </div>
        <div class="gal-filters">
          <div class="gal-bar" data-gallery-years role="group" aria-label="Filter by year"></div>
          <div class="gal-bar" data-gallery-categories role="group" aria-label="Filter by type"></div>
        </div>
        <p class="gal-count" data-gallery-count></p>
        <div class="gal-grid" data-gallery-grid></div>
      </div>
    </section>
  </main>

  <footer class="footer">© <span id="year"></span> Hui Jun (June) Wen · Queens, NY</footer>

  <script src="data/events.js"></script>
  <script src="gallery.js"></script>
  <script src="script.js"></script>
</body>
</html>
```

Create a placeholder `data/events.js` so the page works before Task 13 has run for real:

```bash
mkdir -p data && printf 'window.GALLERY_DATA = { "events": [] };\n' > data/events.js
```

- [ ] **Step 7: Add the nav link on `index.html`**

In the `.nav-links` block of `index.html` (around line 18-22), insert after the Seminars link:

```html
      <a href="events.html">Events</a>
```

- [ ] **Step 8: Check it in a browser**

```bash
open events.html
```
1. With the empty placeholder data, the page shows "Gallery data has not been built yet." and does not throw.
2. The theme toggle and the mobile menu both work — this is what Task 5's guards bought.
3. Nav links back to `index.html` sections resolve.
4. At 375px the grid is two columns with no horizontal scroll.

- [ ] **Step 9: Commit**

```bash
git add events.html gallery.css gallery.js data/events.js index.html \
        tools/tests/js/gallery.test.js
git commit -m "$(printf 'feat: add the filterable event gallery page\n\nevents.html renders entirely from window.GALLERY_DATA, so no photo is\nhardcoded in markup and adding an event means rebuilding data only.\ngallery.js stays a classic script, which keeps file:// working, and keeps\nits filter helpers pure so node --test can exercise them in a vm sandbox.\n\nThe page carries #year, .theme-toggle, .nav-toggle and .nav-links because\nscript.js looks all four up.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 15: Featured strip, pre-publish verification, and docs

**Files:**
- Create: `tools/verify.py`
- Create: `tools/tests/test_verify.py`
- Modify: `index.html` (Partnership section)
- Modify: `script.js` (featured strip renderer)
- Modify: `style.css` (featured strip styles)
- Modify: `README.md`

**Interfaces:**
- Consumes: `data/events.js`, `assets/events/`
- Produces:
  - `verify.check(repo_root: str) -> List[dict]` — each `{"check", "ok", "detail"}`
  - `verify.load_gallery_data(path: str) -> dict` — parses `window.GALLERY_DATA = {...};`
  - CLI: `python3 -m tools.verify` — prints each check, exits 1 if any failed
  - DOM contract: `[data-featured]` container on `index.html`, filled by `script.js` when `window.GALLERY_DATA` exists

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_verify.py
import json
import os
import unittest

from tools import verify
from tools.tests import fixtures


def write_repo(root, data, files, html=""):
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    os.makedirs(os.path.join(root, "assets", "events", "thumbs"), exist_ok=True)
    with open(os.path.join(root, "data", "events.js"), "w") as fh:
        fh.write("window.GALLERY_DATA = %s;\n" % json.dumps(data))
    for rel, size in files:
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"\xff\xd8" + b"\x00" * max(size - 2, 0))
    with open(os.path.join(root, "index.html"), "w") as fh:
        fh.write(html or "<html><body></body></html>")


ONE_EVENT = {
    "events": [{
        "id": "e1", "date": "2026-06-09", "year": "2026", "title": "T",
        "category": "seminar", "category_label": "Health Seminars",
        "physician": "", "partners": [], "featured": True,
        "photos": [{"src": "assets/events/e1-001.jpg",
                    "thumb": "assets/events/thumbs/e1-001.jpg",
                    "w": 1400, "h": 933, "caption": "c", "featured": True}],
    }]
}


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.root = fixtures.make_tempdir()

    def tearDown(self):
        fixtures.cleanup(self.root)

    def results(self):
        return {r["check"]: r for r in verify.check(self.root)}

    def test_passes_a_consistent_repo(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ])
        for name, result in self.results().items():
            self.assertTrue(result["ok"], "%s: %s" % (name, result["detail"]))

    def test_flags_a_referenced_file_that_is_missing(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ])
        self.assertFalse(self.results()["every referenced file exists"]["ok"])

    def test_flags_an_orphan_file_nothing_references(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
            ("assets/events/orphan.jpg", 10 * 1024),
        ])
        self.assertFalse(self.results()["every asset is referenced"]["ok"])

    def test_flags_a_file_over_the_size_cap(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 600 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ])
        self.assertFalse(self.results()["no file over 500 KB"]["ok"])

    def test_flags_a_banned_format_in_assets(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
            ("assets/events/leftover.heic", 1024),
        ])
        self.assertFalse(self.results()["no web-hostile formats in assets"]["ok"])

    def test_flags_an_img_src_in_html_with_no_file(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ], html='<img src="assets/rebrand/ghost-before.jpg" alt="x">')
        self.assertFalse(self.results()["no dead img src in html"]["ok"])

    def test_ignores_remote_and_data_uris_in_html(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ], html='<img src="https://example.com/a.png"><img src="data:image/gif;base64,R0lGOD">')
        self.assertTrue(self.results()["no dead img src in html"]["ok"])

    def test_load_gallery_data_parses_the_js_assignment(self):
        write_repo(self.root, ONE_EVENT, [])
        data = verify.load_gallery_data(os.path.join(self.root, "data", "events.js"))
        self.assertEqual(len(data["events"]), 1)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest tools.tests.test_verify -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.verify'`

- [ ] **Step 3: Implement `tools/verify.py`**

```python
# tools/verify.py
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


def _walk_assets(root):
    base = os.path.join(root, "assets", "events")
    for dirpath, dirnames, filenames in os.walk(base):
        for name in filenames:
            if name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


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

    on_disk = dict(_walk_assets(root))
    orphans = sorted(set(on_disk) - referenced)
    add("every asset is referenced", not orphans, ", ".join(orphans[:5]))

    oversized = ["%s (%d KB)" % (rel, os.path.getsize(full) // 1024)
                 for rel, full in sorted(on_disk.items())
                 if os.path.getsize(full) > MAX_FILE_BYTES]
    add("no file over 500 KB", not oversized, ", ".join(oversized[:5]))

    banned = [rel for rel in sorted(on_disk) if rel.lower().endswith(BANNED_EXTS)]
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
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m unittest tools.tests.test_verify -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Replace the Partnership photos with the featured strip**

In `index.html`, replace the `<div class="photos">…</div>` block at lines 129-132 with:

```html
        <div class="photos" data-featured>
          <figure><img data-slot="Event photo: community fest" src="assets/event_1.jpg" alt="Rendr team at a community event booth" loading="lazy"><figcaption>Rendr as Title Sponsor of the 2026 Joint Picnic &amp; Cultural Fest</figcaption></figure>
          <figure><img data-slot="Event photo: health seminar" src="assets/event_2.jpg" alt="Physician presenting at a community health seminar" loading="lazy"><figcaption>Physician-led seminar on managing and relieving constipation</figcaption></figure>
        </div>
        <p class="more"><a href="events.html">See all events →</a></p>
```

The two existing figures stay as the fallback: if `data/events.js` has no featured photos, the section looks exactly as it does today.

- [ ] **Step 6: Render the strip in `script.js`**

Append to `script.js`:

```javascript
// Featured event strip on the home page. Falls back to whatever markup is
// already in [data-featured] when no gallery data has been built yet.
(function () {
  const host = document.querySelector("[data-featured]");
  const data = window.GALLERY_DATA;
  if (!host || !data || !Array.isArray(data.events)) return;

  const featured = [];
  data.events.forEach((event) =>
    (event.photos || []).forEach((photo) => {
      if (photo.featured) featured.push({ event, photo });
    })
  );
  if (featured.length === 0) return;

  host.textContent = "";
  featured.slice(0, 8).forEach(({ event, photo }) => {
    const fig = document.createElement("figure");
    const img = document.createElement("img");
    img.src = photo.thumb || photo.src;
    img.width = photo.w || 0;
    img.height = photo.h || 0;
    img.alt = photo.caption || event.title;
    img.loading = "lazy";
    img.decoding = "async";
    const cap = document.createElement("figcaption");
    cap.textContent = photo.caption || event.title;
    fig.append(img, cap);
    host.append(fig);
  });
  host.classList.add("featured-grid");
})();
```

Add `<script src="data/events.js"></script>` immediately before `<script src="script.js"></script>` in `index.html`.

- [ ] **Step 7: Style the strip**

Append to `style.css`:

```css
/* Featured event strip */
.featured-grid { grid-template-columns: repeat(4, 1fr); }
.featured-grid figcaption { font-size: .8rem; color: var(--muted); }
.more { margin-top: 1rem; }
.more a { color: var(--accent); font-weight: 600; text-decoration: none; }
.more a:hover { text-decoration: underline; }
@media (max-width: 900px) { .featured-grid { grid-template-columns: 1fr 1fr; } }
```

Note `.photos` already sets `display: grid`, so `.featured-grid` only overrides the column count.

- [ ] **Step 8: Run every test and the verifier**

```bash
python3 -m unittest discover -s tools/tests -t . -v
export PATH="$HOME/.local/bin:$PATH" && node --test tools/tests/js/
python3 -m tools.verify
```
Expected: all Python tests pass, all 10 JS tests pass, and every verifier check reports `ok`. With only the placeholder `data/events.js`, "every asset is referenced" passes because there are no assets under `assets/events/` yet.

- [ ] **Step 9: Check both pages in a browser**

```bash
open index.html
```
1. The Partnership section still shows its two photos (or the featured grid, once real data exists).
2. "See all events →" reaches `events.html`.
3. Case 02 before/after still switches.
4. No console errors on either page, in light and dark mode, at 375px and at full width.

- [ ] **Step 10: Update the README**

Replace the `## Images` section with:

```markdown
## Images

Files in `assets/`. A missing file shows a labeled placeholder.

| File | Status |
|---|---|
| `flyer_1.jpg` … `flyer_7.jpg` | ✅ Seminar flyers (rendered from the original PDFs) |
| `event_1.jpg`, `event_2.jpg` | ✅ Fallback community photos, shown until the gallery is built |
| `digital_*.jpg` | ✅ WeChat Video / WeChat articles / RedNote screenshots |
| `headshot.jpg` | ✅ Headshot |
| `rebrand/*-before.jpg`, `rebrand/*-after.jpg` | ✅ 5 featured before/after signage pairs (32 available, see `tools/out/rebrand-pairs.json`) |
| `events/`, `events/thumbs/` | Generated — curated event photos and thumbnails |
| `Hui_Jun_Wen_Resume.pdf` | ✅ Final résumé |

## Pages

| Page | Contents |
|---|---|
| `index.html` | One-page portfolio, 4 case studies, featured event strip |
| `events.html` | Filterable event gallery, rendered from `data/events.js` |

`data/events.js` assigns `window.GALLERY_DATA` and is loaded with a plain
`<script>` tag, not `fetch()`, so both pages work opened directly as `file://`.

## Tooling

Everything in `tools/` is read-only with respect to the OneDrive archive. It
needs no dependencies: Python 3.9 standard library plus macOS `sips`.

```bash
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

## Tests

```bash
python3 -m unittest discover -s tools/tests -t .
node --test tools/tests/js/
```
```

- [ ] **Step 11: Commit**

```bash
git add tools/verify.py tools/tests/test_verify.py index.html script.js style.css README.md
git commit -m "$(printf 'feat: add featured event strip and pre-publish verification\n\nverify.py checks asset references in both directions, since the defect\nthis work started from was an <img> pointing at a file that was never\nadded. It also enforces the size budget and refuses HEIC, JFIF, TIF, DNG,\nMOV and ZIP in assets/.\n\nThe featured strip degrades to the two existing photos when no gallery\ndata has been built, so index.html is never worse than it is today.\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>')"
```

---

## Appendix: runbook

What June actually does, and when.

| Phase | Command | Needs June | Waits on sync? |
|---|---|---|---|
| Audit | `python3 -m tools.manifests --archive "$ARCHIVE"` | — | No |
| Rebrand | `python3 -m tools.build_rebrand --archive "$ARCHIVE" --limit 5` | pick 5 pairs | ~10 files |
| Cleanup | read `tools/out/duplicates.csv`, then `bash tools/out/cleanup.sh --apply` | **yes** | No |
| Pick events | tick rows in `tools/out/events-manifest.md` | **yes** | No |
| Download | `python3 -m tools.hydrate --archive "$ARCHIVE" --manifest …` | — | yes, ~4 GB |
| Pick photos | `python3 -m tools.thumbs …` then `open tools/picker/index.html` | **yes** | yes |
| Publish | `python3 -m tools.build_assets --archive "$ARCHIVE" --selection …` | — | — |
| Verify | `python3 -m tools.verify` | — | — |

Two archive questions only June can answer, both surfaced under "Needs your
decision" in `events-manifest.md`:

1. `Centerlight Health Fair` — is it **2023-11-13** or **2023-11-23**? The same
   27 HEIC files are filed under both.
2. Three empty folders (`3.29 Dr. David Zhuang Health Talk`,
   `UCA (Cultural)  Event`, `2026 Event/October Event`) — were photos never
   added, or were they filed elsewhere?

The tooling never guesses either one.
