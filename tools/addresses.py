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
_ADDRESS = re.compile(r"^([\d\-]+)\s+([a-z0-9]+)", re.I)
# A dash with whitespace on at least one side is a genuine word separator
# ("Group - 833 58th St"). A dash with no surrounding whitespace is always
# inside a house-number range ("136-20", "42-66") or a typo'd separator
# ("Fang-730") and must not be treated as a word boundary.
_LOOSE_DASH = re.compile(r"\s[-–]|[-–]\s")
_PREFIX_LOOSE = re.compile(r"^(.*?)(?:\s[-–]|[-–]\s)\s*")
# A real, complete address is either the whole remaining text, or is
# immediately followed by a recognized street-type word. Used to tell a
# genuine address ("136-20 38th St", followed by nothing or "- 2024
# Renovation") apart from a practice name that merely starts with the same
# digits as the real address ("833 Janlian Medical Group", followed by
# "Medical Group", not a street-type word).
_STREET_SUFFIX = re.compile(
    r"^(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|pl|"
    r"place|ct|court|hwy|highway|pkwy|pwky|parkway|way|cir|circle|plaza|"
    r"ter|terrace)\.?$",
    re.I,
)


def _is_complete_address(tail):
    """Is `tail` -- whatever immediately follows a matched street word --
    consistent with that match being a genuine, self-contained address?"""
    tail = tail.strip()
    if not tail:
        return True
    return bool(_STREET_SUFFIX.match(tail.split()[0]))


def _best_address_match(s):
    """Return the _ADDRESS match that best represents the address in `s`.

    A loose (whitespace-adjacent) dash usually separates a practice name
    from the address that follows it ("Dr. Hall - 2251 86th St"). Two
    real-archive shapes break a naive "always prefer the text after the
    dash" rule, so the two sides are evaluated and chosen between on
    evidence rather than tried in a fixed order:

    - A practice name can itself start with the location's own house
      number ("833 Janlian Medical Group - 833 58th St") -- syntactically
      number-first, but not a complete address, so the right side wins.
    - A complete address can be followed by unrelated trailing text
      ("136-20 38th St - 2024 Renovation") -- here the left side is the
      complete, self-contained address, so it wins even though it is also
      number-first.

    The left side wins only when it parses as an address AND is complete
    per `_is_complete_address`; otherwise the right side wins if it
    parses; otherwise an incomplete left match is used as a last resort.

    A tight dash (no adjacent whitespace, as in a house-number range or a
    typo'd separator like "Fang-730") is never treated as a split point
    here -- it falls through to the direct match / any-dash fallback
    below instead.
    """
    if _LOOSE_DASH.search(s):
        m = _PREFIX_LOOSE.match(s)
        if m:
            left = m.group(1).strip()
            right = s[m.end():].strip()
            left_m = _ADDRESS.match(left)
            if left_m and _is_complete_address(left[left_m.end():]):
                return left_m
            right_m = _ADDRESS.match(right)
            if right_m:
                return right_m
            if left_m:
                return left_m
    direct = _ADDRESS.match(s)
    if direct:
        return direct
    # Last resort: a typo'd separator with no surrounding whitespace
    # ("Dr. Chixin Fang-730 58th Street"). Strip at the first dash of any
    # kind.
    stripped = _PREFIX.sub("", s, count=1).strip()
    return _ADDRESS.match(stripped)


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
    candidate = _best_address_match(s)
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
    """Human label: the address portion of the after-side folder name.

    Mirrors normalize()'s loose-dash-first decision (see
    _best_address_match) instead of always stripping at the first dash of
    any kind, so a tight dash inside the practice name -- as in "Medical
    Imaging-Urgent Care - 729 61st ST" -- doesn't leave a leftover prefix
    fragment ("Urgent Care - 729 61st ST") in text that ends up as a
    user-visible caption.

    This matches directly against `name` -- never a lowercased copy --
    and relies on _ADDRESS/_STREET_SUFFIX being case-insensitive (re.I)
    to recognize "Mott"/"St"/"ST" etc. in their original casing. A prior
    version matched against name.lower() to decide where to split and
    then sliced `name` using those offsets; str.lower() is not
    length-preserving for every Unicode character (e.g. U+0130 "İ"
    lowercases to two code points), so an offset computed on the
    lowercased copy can land one or more characters into `name`,
    silently truncating the caption. Matching on `name` itself keeps
    every offset native to the string being sliced.
    """
    name = os.path.basename(after_dir)
    if _LOOSE_DASH.search(name):
        m = _PREFIX_LOOSE.match(name)
        if m:
            left = m.group(1).strip()
            right = name[m.end():].strip()
            left_m = _ADDRESS.match(left)
            if left_m and _is_complete_address(left[left_m.end():]):
                return left or name
            if _ADDRESS.match(right):
                return right or name
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
