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
    # A bare, unpopulated month container -- not an event itself.
    ("2026 Event", "October Event"),
    # A genuine empty event nested two levels deep under the month layer.
    ("2026 Event", "April Event/4.2.2026 - HCS Q2 Birthday Party- Bensonhurst"),
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
