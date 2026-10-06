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
