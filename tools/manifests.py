"""Write the four organize-it-yourself deliverables plus the picking sheet."""
import argparse
import csv
import os
import re
import shlex
import stat
import sys

from tools import classify, dupes, eventdata, naming, scan

GB = 1024.0 ** 3

_TICK_ROW = re.compile(r"^\|\s*\[([xX ])\]\s*\|.*\|\s*`([^`]+)`\s*\|\s*$")


def _read_ticked_ids(path):
    """Ids whose row is already ticked `[x]` in an existing manifest at
    `path`. Re-running the audit is the documented way to confirm the
    archive hasn't changed (see README/spec), so regenerating this file
    must never silently erase hours of a non-engineer's manual ticking.
    Returns an empty set when `path` does not exist yet (first run)."""
    if not os.path.exists(path):
        return set()
    ticked = set()
    with open(path) as fh:
        for line in fh:
            m = _TICK_ROW.match(line.rstrip("\n"))
            if m and m.group(1).strip().lower() == "x":
                ticked.add(m.group(2))
    return ticked


def is_removed_duplicate(event, duplicate_keys):
    """True only for the catch-all copy that dupes.analyze() proved mirrors
    a sibling event folder elsewhere in the archive.

    A catch-all folder's (top, year, event) is indistinguishable from its
    non-catchall sibling's own identity -- analyze() only tells the two
    apart via the `catchall` flag -- so that flag has to be checked here
    too, or this would also swallow the legitimate original. A catch-all
    folder that `duplicate_keys` does NOT cover (dupes.analyze() calls this
    "unmatched") is never treated as a duplicate here either: it has no
    sibling anywhere in the archive, so its photos are real and distinct,
    merely filed inside a folder that happens to be named in scan.CATCHALLS.
    """
    return event["catchall"] and (event["top"], event["year"], event["event"]) in duplicate_keys


def write_events_manifest(events, analysis, conflicts, duplicate_keys, path,
                          global_dupes=None, empty_months=None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    previously_ticked = _read_ticked_ids(path)
    ticked = previously_ticked & {e["id"] for e in events}
    stale = previously_ticked - ticked
    lines = []
    lines.append("# Event manifest\n")
    lines.append("Tick the events you want in the portfolio gallery, then run")
    lines.append("`python3 -m tools.hydrate --events <id> <id> ...`\n")
    if previously_ticked:
        note = ("_Re-run of an existing manifest: %d previously ticked row(s) "
                "were carried forward by event id." % len(ticked))
        if stale:
            note += (" %d ticked id(s) from the old file no longer match any "
                     "event this run and were dropped: %s."
                     % (len(stale), ", ".join("`%s`" % s for s in sorted(stale))))
        note += " New or renamed events start unticked._\n"
        lines.append(note)
    # `events` includes one record per catch-all mirror folder too (it needs
    # those to compute per-folder photo/byte counts), so the unique-event
    # count June actually cares about excludes only the folders proven to be
    # duplicates -- not every folder merely sitting inside a catch-all-named
    # directory. See is_removed_duplicate().
    unique_events = [e for e in events if not is_removed_duplicate(e, duplicate_keys)]
    unique_empty = [e for e in unique_events if e["photos"] == 0]
    lines.append("- %d unique events (%d with photos, %d empty folders)"
                 % (len(unique_events), len(unique_events) - len(unique_empty),
                    len(unique_empty)))
    lines.append("- cleanup.sh can safely move %d files (%.2f GB) -- duplicates "
                 "inside catch-all folders, matched to a sibling event folder"
                 % (analysis["removable_files"], analysis["removable_bytes"] / GB))
    if global_dupes is not None:
        outside = global_dupes["files"] - analysis["removable_files"]
        outside_bytes = (global_dupes["bytes"] - analysis["removable_bytes"]) / GB
        lines.append(
            "- the archive's *total* name+size duplication is larger: %d files "
            "(%.2f GB). The extra %d files (%.2f GB) are duplicates that live "
            "**outside** catch-all folders -- picking which copy to keep needs "
            "a person, so cleanup.sh does not touch them. **cleanup.sh only "
            "reclaims the %.2f GB figure above, not this one.**"
            % (global_dupes["files"], global_dupes["bytes"] / GB,
               outside, outside_bytes, analysis["removable_bytes"] / GB))
    lines.append("")

    if conflicts:
        lines.append("## Needs your decision\n")
        lines.append("The archive gives one event two different dates:\n")
        for c in conflicts:
            lines.append("- **%s** — %s" % (c["title"], " vs ".join(c["dates"])))
            for p in c["paths"]:
                lines.append("  - `%s`" % p)
        lines.append("")

    empties = [e for e in events
               if e["photos"] == 0 and not is_removed_duplicate(e, duplicate_keys)]
    if empties:
        lines.append("## Empty folders\n")
        lines.append("%d event folders exist but hold no photos:\n" % len(empties))
        for e in empties:
            lines.append("- `%s`" % e["dir"])
        lines.append("")

    if empty_months:
        lines.append("## Empty month folders\n")
        lines.append("%d month folder(s) exist but have no events filed under "
                     "them yet -- not events themselves, just unused buckets:\n"
                     % len(empty_months))
        for rel, _top, _year, _month in empty_months:
            lines.append("- `%s`" % rel)
        lines.append("")

    by_category = {}
    for e in events:
        if is_removed_duplicate(e, duplicate_keys):
            continue
        by_category.setdefault(e["category"], []).append(e)

    for cid in classify.CATEGORIES:
        group = by_category.get(cid)
        if not group:
            continue
        note = "  ← not recommended for publication" if cid == "internal" else ""
        lines.append("## %s (%d events)%s\n" % (classify.LABELS[cid], len(group), note))
        if cid == "other":
            lines.append(
                "> Caution: this catch-all bucket can include internal/staff-facing "
                "events that just don't match the other keyword rules (for example, "
                "insurance-enrollment events like \"Anthem BCBS Health Care AEEP In "
                "Roll\" or \"UHC 2026 AEP Rollout Dinner - Flushing\"). Check each "
                "row here before publishing, the same way you would for "
                "Internal / Provider.\n")
        lines.append("| pick | date | event | photos | physician | partners | id |")
        lines.append("|---|---|---|---|---|---|---|")
        for e in group:
            mark = "x" if e["id"] in ticked else " "
            lines.append("| [%s] | %s | %s | %d | %s | %s | `%s` |" % (
                mark,
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
    return {"carried": len(ticked), "stale": len(stale)}


def write_rename_plan(events, duplicate_keys, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    kept = [e for e in events if not is_removed_duplicate(e, duplicate_keys)]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["current_path", "current_name", "proposed_name",
                         "photos", "category"])
        for e in kept:
            writer.writerow([e["dir"], e["event"], e["proposed"],
                             e["photos"], e["category"]])
    return len(kept)


_HEADER = """#!/usr/bin/env bash
# Generated by tools/manifests.py on {stamp}. Review before running.
#
# Moves duplicate files into the quarantine folder below. Nothing is
# deleted. Re-run {undo_name} to reverse every move.
#
#   bash {script_name}            # dry run, prints what would move
#   bash {script_name} --apply    # actually move
#
# Quarantine: {quarantine_dir}
#
# After checking the quarantine folder, delete it from the OneDrive web UI,
# which keeps a 93-day recycle bin.
set -euo pipefail

APPLY=0
[[ "${{1:-}}" == "--apply" ]] && APPLY=1
if [[ $APPLY -eq 0 ]]; then
  echo "DRY RUN -- nothing will move. Re-run with --apply to act."
fi

MOVED=0
SKIPPED=0
QUEUED={count}

"""

_UNDO_HEADER = """#!/usr/bin/env bash
# Generated by tools/manifests.py on {stamp}. Reverses {script_name}.
#
#   bash {undo_name}            # dry run, prints what would restore
#   bash {undo_name} --apply    # actually restore
set -euo pipefail

APPLY=0
[[ "${{1:-}}" == "--apply" ]] && APPLY=1
if [[ $APPLY -eq 0 ]]; then
  echo "DRY RUN -- nothing will move. Re-run with --apply to act."
fi

MOVED=0
SKIPPED=0
QUEUED={count}

"""

_FOOTER = """
if [[ $APPLY -eq 1 ]]; then
  echo "Moved $MOVED of $QUEUED queued files into {quarantine_dir} ($SKIPPED skipped)"
  echo "Reverse with: bash {undo_name} --apply"
  if [[ $MOVED -eq 0 && $QUEUED -gt 0 ]]; then
    echo "error: 0 files moved out of $QUEUED queued -- nothing was quarantined. Is the archive path still correct?" >&2
    exit 1
  fi
else
  echo "{count} files would move. Re-run with --apply."
fi
"""

_UNDO_FOOTER = """
if [[ $APPLY -eq 1 ]]; then
  echo "Restored $MOVED of $QUEUED queued files from {quarantine_dir} ($SKIPPED skipped)"
  if [[ $MOVED -eq 0 && $QUEUED -gt 0 ]]; then
    echo "error: 0 files restored out of $QUEUED queued -- nothing was found in the quarantine folder." >&2
    exit 1
  fi
else
  echo "{count} files would be restored. Re-run with --apply."
fi
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


def _move_block(src_abs, dst_abs, rel, verb, skip_label):
    """One self-contained, fully-quoted guarded move.

    Every path is resolved to an absolute path and quoted with shlex.quote
    at generation time -- there is no shell-variable path-building to get
    wrong, and real folder names in this archive contain spaces, '&', '#',
    parentheses and apostrophes.

    In --apply mode this also counts: MOVED increments on every successful
    `mv` (and echoes it, so a successful move is no longer silent), SKIPPED
    increments when the source is missing. The footer then reports real
    totals instead of the queued count. `skip_label` differs by direction
    -- "already gone" reads as data loss when echoed by the undo script,
    which means the opposite (the file was never quarantined to begin
    with), so the two scripts use different wording for the same branch.
    """
    src_q = shlex.quote(src_abs)
    dst_q = shlex.quote(dst_abs)
    dstdir_q = shlex.quote(os.path.dirname(dst_abs))
    rel_q = shlex.quote(rel)
    done_label_q = shlex.quote("%sd:" % verb)
    would_label_q = shlex.quote("would %s:" % verb)
    skip_label_q = shlex.quote("%s:" % skip_label)
    return (
        "if [[ -e %s ]]; then\n"
        "  if [[ $APPLY -eq 1 ]]; then\n"
        "    mkdir -p %s\n"
        "    mv %s %s\n"
        "    MOVED=$((MOVED + 1))\n"
        "    printf '%%s %%s\\n' %s %s\n"
        "  else\n"
        "    printf '%%s %%s\\n' %s %s\n"
        "  fi\n"
        "else\n"
        "  SKIPPED=$((SKIPPED + 1))\n"
        "  printf '%%s %%s\\n' %s %s\n"
        "fi\n"
    ) % (src_q, dstdir_q, src_q, dst_q,
         done_label_q, rel_q,
         would_label_q, rel_q,
         skip_label_q, rel_q)


def write_cleanup(analysis, archive_root, path, undo_path, stamp):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    rels = _removable(analysis)
    quarantine_name = "_DUPLICATES_%s" % stamp
    archive_abs = os.path.abspath(archive_root)
    quarantine_abs = os.path.join(archive_abs, quarantine_name)
    script_name = os.path.basename(path)
    undo_name = os.path.basename(undo_path)

    with open(path, "w") as fh:
        fh.write(_HEADER.format(stamp=stamp, script_name=script_name,
                                undo_name=undo_name,
                                quarantine_dir=quarantine_abs,
                                count=len(rels)))
        for rel in rels:
            src_abs = os.path.join(archive_abs, rel)
            dst_abs = os.path.join(quarantine_abs, rel)
            fh.write(_move_block(src_abs, dst_abs, rel, "move", "skip (already gone)"))
        fh.write(_FOOTER.format(count=len(rels), quarantine_dir=quarantine_abs,
                                undo_name=undo_name))
    _chmod_x(path)

    with open(undo_path, "w") as fh:
        fh.write(_UNDO_HEADER.format(stamp=stamp, script_name=script_name,
                                     undo_name=undo_name,
                                     count=len(rels)))
        for rel in rels:
            src_abs = os.path.join(archive_abs, rel)      # original location
            dst_abs = os.path.join(quarantine_abs, rel)    # quarantined location
            fh.write(_move_block(dst_abs, src_abs, rel, "restore", "skip (not quarantined)"))
        fh.write(_UNDO_FOOTER.format(count=len(rels), quarantine_dir=quarantine_abs))
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
    global_dupes = dupes.global_redundancy(rows)
    dupes.write_csv(analysis, os.path.join(out, "duplicates.csv"))
    events = eventdata.collect_events(
        rows, extra_dirs=eventdata.find_empty_event_dirs(args.archive))
    empty_months = eventdata.find_empty_month_dirs(args.archive)
    duplicate_keys = dupes.duplicate_event_keys(analysis)
    conflicts = naming.find_conflicts([
        {"name": e["event"], "iso": e["iso"], "path": e["dir"]}
        for e in events if not is_removed_duplicate(e, duplicate_keys)
    ])
    manifest_path = os.path.join(out, "events-manifest.md")
    had_existing = os.path.exists(manifest_path)
    tick_stats = write_events_manifest(events, analysis, conflicts, duplicate_keys,
                                       manifest_path,
                                       global_dupes=global_dupes, empty_months=empty_months)
    write_rename_plan(events, duplicate_keys, os.path.join(out, "rename-plan.csv"))
    moves = write_cleanup(analysis, args.archive,
                          os.path.join(out, "cleanup.sh"),
                          os.path.join(out, "undo.sh"), args.stamp)

    kept_events = [e for e in events if not is_removed_duplicate(e, duplicate_keys)]
    empties = len([e for e in kept_events if e["photos"] == 0])
    print("files        %d (%.1f GB)" % (inv_stats["files"], inv_stats["bytes"] / GB))
    print("downloaded   %.1f%%" % (100.0 * inv_stats["hydrated"] / max(inv_stats["files"], 1)))
    print("events       %d (%d empty folders, %d empty month folders)"
          % (len(kept_events), empties, len(empty_months)))
    print("duplicates   scriptable: %d files, %.2f GB  |  global: %d files, %.2f GB"
          % (analysis["removable_files"], analysis["removable_bytes"] / GB,
             global_dupes["files"], global_dupes["bytes"] / GB))
    print("conflicts    %d" % len(conflicts))
    print("cleanup.sh   %d moves queued (dry run by default)" % moves)
    if had_existing:
        print("manifest     re-generated %s: carried forward %d previously "
              "ticked row(s)%s -- nothing was erased"
              % (manifest_path, tick_stats["carried"],
                 (", %d stale tick(s) dropped (event no longer exists this run)"
                  % tick_stats["stale"]) if tick_stats["stale"] else ""))
    print("\nwrote %s/{inventory.csv,duplicates.csv,events-manifest.md,"
          "rename-plan.csv,cleanup.sh,undo.sh}" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
