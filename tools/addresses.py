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
# A dash with whitespace on at least one side is a genuine word separator
# ("Group - 833 58th St"). A dash with no surrounding whitespace is always
# inside a house-number range ("136-20", "42-66") or a typo'd separator
# ("Fang-730") and must not be treated as a word boundary.
_LOOSE_DASH = re.compile(r"\s[-–]|[-–]\s")
_PREFIX_LOOSE = re.compile(r"^.*?(?:\s[-–]|[-–]\s)\s*")


def normalize(name):
    """Return "<housenumber> <streetword>", or None if there is no address."""
    s = name.lower()
    # Strip a real trailing file extension only (dot + short alnum run at
    # the very end). os.path.splitext is unsafe here: "Dr. Hall - 2251
    # 86th St" has its first "." right after "Dr", so splitext((...))[0]
    # would truncate it to "dr" and destroy the address.
    s = re.sub(r"\.[a-z0-9]{1,5}$", "", s)
    s = s.split("(")[0]
    # A trailing " - Logo", " - Interior Logo" etc. is a photo descriptor.
    s = re.sub(r"\s*-\s*(exterior|interior|entrance|hallway|front|building|waiting|floor)\b.*$", "", s)
    s = re.sub(r"\s*-\s*[a-z ]*logo\s*$", "", s)
    s = re.sub(r"\s*-\s*[a-z ]*directory\s*$", "", s)
    s = _SUFFIX.sub("", s)
    s = s.strip()
    candidate = None
    # When a real separator dash is present, the address almost always
    # follows it ("833 Janlian Medical Group - 833 58th St" must not match
    # on the leading "833 Janlian" just because it also looks number-first).
    if _LOOSE_DASH.search(s):
        stripped = _PREFIX_LOOSE.sub("", s, count=1).strip()
        candidate = _ADDRESS.match(stripped)
    if not candidate:
        candidate = _ADDRESS.match(s)
    if not candidate:
        # Last resort: a typo'd separator with no surrounding whitespace
        # ("Dr. Chixin Fang-730 58th Street"). Strip at the first dash of
        # any kind.
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
