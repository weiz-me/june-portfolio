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
