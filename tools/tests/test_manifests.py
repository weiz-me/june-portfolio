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
        self.duplicate_keys = dupes.duplicate_event_keys(self.analysis)
        self.conflicts = naming.find_conflicts([
            {"name": e["event"], "iso": e["iso"], "path": e["event"]}
            for e in self.events
        ])

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def test_manifest_lists_every_event_and_the_conflicts(self):
        path = os.path.join(self.work, "events-manifest.md")
        manifests.write_events_manifest(self.events, self.analysis, self.conflicts,
                                        self.duplicate_keys, path)
        with open(path) as fh:
            text = fh.read()
        for e in self.events:
            self.assertIn(e["title"], text)
        self.assertIn("Centerlight", text)
        self.assertIn("needs your decision", text.lower())

    def test_rerunning_preserves_existing_ticks_by_event_id(self):
        # Re-running the audit is the documented way to confirm the archive
        # hasn't changed; it must never silently wipe a manifest a human
        # has already spent hours ticking (I5).
        path = os.path.join(self.work, "events-manifest.md")
        manifests.write_events_manifest(self.events, self.analysis, self.conflicts,
                                        self.duplicate_keys, path)
        with open(path) as fh:
            first = fh.read()

        some_id = next(e["id"] for e in self.events if e["photos"] > 0)
        ticked_line = next(line for line in first.splitlines()
                           if "`%s`" % some_id in line)
        first = first.replace(ticked_line, ticked_line.replace("[ ]", "[x]", 1))
        with open(path, "w") as fh:
            fh.write(first)

        stats = manifests.write_events_manifest(
            self.events, self.analysis, self.conflicts, self.duplicate_keys, path)
        self.assertEqual(stats["carried"], 1)
        self.assertEqual(stats["stale"], 0)

        with open(path) as fh:
            regenerated = fh.read()
        regenerated_line = next(line for line in regenerated.splitlines()
                                if "`%s`" % some_id in line)
        self.assertIn("[x]", regenerated_line)

        # Every other row must still start unticked.
        other_rows = [line for line in regenerated.splitlines()
                     if line.startswith("| [") and ("`%s`" % some_id) not in line]
        self.assertTrue(other_rows)
        self.assertTrue(all("[ ]" in line for line in other_rows))

    def test_rerunning_reports_a_stale_tick_for_an_id_that_no_longer_exists(self):
        path = os.path.join(self.work, "events-manifest.md")
        manifests.write_events_manifest(self.events, self.analysis, self.conflicts,
                                        self.duplicate_keys, path)
        with open(path) as fh:
            text = fh.read()
        with open(path, "w") as fh:
            fh.write(text.replace(
                "| [ ] |", "| [x] |", 1).rstrip("\n")
                + "\n| [x] | 2099-01-01 | Ghost Event | 0 |  |  | `ghost-event-id` |\n")

        stats = manifests.write_events_manifest(
            self.events, self.analysis, self.conflicts, self.duplicate_keys, path)
        self.assertEqual(stats["stale"], 1)

    def test_orphan_catchall_event_is_a_tickable_row_but_its_mirror_is_not(self):
        # "2022"/"2023" are catch-all folder names (scan.CATCHALLS), but not
        # every folder inside one is a duplicate. An orphan catch-all event
        # (no sibling anywhere in the archive) must still appear as a normal
        # tickable row -- while a verified mirror (byte-identical to its
        # sibling) must not, or it would double-count the same photos.
        orphan_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                                  "2022", "9999 Orphan Event")
        os.makedirs(orphan_dir)
        fixtures.make_seed_image(os.path.join(orphan_dir, "a.jpg"), "jpg")

        rows = list(scan.walk(self.archive_root))
        events = eventdata.collect_events(rows)
        analysis = dupes.analyze(rows)
        duplicate_keys = dupes.duplicate_event_keys(analysis)
        conflicts = naming.find_conflicts([
            {"name": e["event"], "iso": e["iso"], "path": e["event"]} for e in events
        ])

        path = os.path.join(self.work, "events-manifest.md")
        manifests.write_events_manifest(events, analysis, conflicts, duplicate_keys, path)
        with open(path) as fh:
            text = fh.read()

        self.assertIn("| [ ] |", text)
        orphan_line = next(line for line in text.splitlines() if "Orphan Event" in line)
        self.assertIn("[ ]", orphan_line)

        # The verified mirror of "1023 Rendr Dinner" must not get its own row:
        # its title shows up once (from the real folder), not duplicated.
        rendr_rows = [line for line in text.splitlines()
                     if line.startswith("| [ ] |") and "Rendr Dinner" in line]
        self.assertEqual(len(rendr_rows), 1)

    def test_rename_plan_has_a_row_per_non_duplicate_event(self):
        path = os.path.join(self.work, "rename-plan.csv")
        count = manifests.write_rename_plan(self.events, self.duplicate_keys, path)
        expected = len([e for e in self.events
                       if not manifests.is_removed_duplicate(e, self.duplicate_keys)])
        self.assertEqual(count, expected)
        self.assertLess(count, len(self.events))
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
        # Compare full relative paths, not basenames: a dry run that moved
        # every file to a different directory while keeping filenames intact
        # would still pass a basename-only comparison. This is the most
        # dangerous script in the project, so the guard has to catch a
        # same-name-different-place move, not just a renamed/deleted one.
        script = os.path.join(self.work, "cleanup.sh")
        manifests.write_cleanup(self.analysis, self.archive_root, script,
                                os.path.join(self.work, "undo.sh"), "2026-10-05")
        before = sorted(
            os.path.relpath(os.path.join(dp, f), self.archive_root)
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        proc = subprocess.run(["bash", script], capture_output=True, text=True)
        after = sorted(
            os.path.relpath(os.path.join(dp, f), self.archive_root)
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
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
