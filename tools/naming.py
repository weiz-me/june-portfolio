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
