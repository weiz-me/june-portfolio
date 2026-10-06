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
