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

    def test_signage_folder_is_never_a_sibling_even_with_a_slug_and_key_collision(self):
        # A signage folder outside "Event Photos" that happens to share both
        # its name (so its slug collides) and a file's (name, size) with a
        # catch-all event folder must never be treated as that event's
        # sibling: signage trees can never legitimately be an event's
        # original copy.
        signage_dir = os.path.join(self.archive_root, "_Original Excelsior Photos",
                                   "Brooklyn", "George Hall, MD - 2251 86th St")
        signage_file = os.path.join(signage_dir, "IMG_0001.jpg")

        catchall_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                                    "2022", "George Hall, MD - 2251 86th St")
        os.makedirs(catchall_dir)
        # A true copy, so (name, size) is identical by construction -- no
        # dependency on image-encoder determinism.
        shutil.copy2(signage_file, os.path.join(catchall_dir, "IMG_0001.jpg"))

        result = dupes.analyze(self.rows())
        full_events = [e["event"] for e in result["full"]]
        unmatched_events = [u["event"] for u in result["unmatched"]]
        self.assertNotIn("George Hall, MD - 2251 86th St", full_events)
        self.assertIn("George Hall, MD - 2251 86th St", unmatched_events)


class TestDuplicateEventKeys(fixtures.ArchiveFixture, unittest.TestCase):
    def rows(self):
        return list(scan.walk(self.archive_root))

    def test_a_mirrored_catchall_is_in_the_set_an_orphan_is_not(self):
        orphan = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                              "2022", "9999 Orphan Event")
        os.makedirs(orphan)
        fixtures.make_seed_image(os.path.join(orphan, "a.jpg"), "jpg")

        result = dupes.analyze(self.rows())
        keys = dupes.duplicate_event_keys(result)

        self.assertIn(("Event Photos", "2022 Events", "1023 Rendr Dinner"), keys)
        self.assertNotIn(("Event Photos", "2022 Events", "9999 Orphan Event"), keys)

    def test_partial_overlap_event_is_in_the_set(self):
        extra_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                                 "2022", "1023 Rendr Dinner")
        fixtures.make_seed_image(os.path.join(extra_dir, "UNIQUE_9999.jpg"), "jpg")
        result = dupes.analyze(self.rows())
        self.assertIn("1023 Rendr Dinner", [p["event"] for p in result["partial"]])
        keys = dupes.duplicate_event_keys(result)
        self.assertIn(("Event Photos", "2022 Events", "1023 Rendr Dinner"), keys)


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
