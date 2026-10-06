import unittest

from tools import eventdata, scan
from tools.tests import fixtures


class TestYearHint(unittest.TestCase):
    def test_extracts_the_year(self):
        self.assertEqual(eventdata.year_hint("2022 Events"), 2022)
        self.assertEqual(eventdata.year_hint("2026 Event"), 2026)

    def test_none_when_absent(self):
        self.assertIsNone(eventdata.year_hint(None))
        self.assertIsNone(eventdata.year_hint("_Completed Installation Photos"))


class TestCollectEvents(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        # Empty folders hold no files, so they only appear via extra_dirs.
        self.events = eventdata.collect_events(
            list(scan.walk(self.archive_root)),
            extra_dirs=eventdata.find_empty_event_dirs(self.archive_root),
        )

    def by_title(self, needle):
        return next(e for e in self.events if needle in e["title"])

    def test_one_entry_per_unique_event(self):
        titles = [e["title"] for e in self.events]
        self.assertEqual(len(titles), len(set(e["id"] for e in self.events)))

    def test_resolves_dates_using_the_year_folder(self):
        self.assertEqual(self.by_title("Blood Pressure Seminar")["iso"], "2022-05-12")

    def test_carries_category_and_counts(self):
        dinner = self.by_title("Rendr Dinner")
        self.assertEqual(dinner["category"], "internal")
        self.assertEqual(dinner["photos"], 3)
        self.assertGreater(dinner["bytes"], 0)

    def test_extracts_physician_and_partners(self):
        seminar = self.by_title("Xian Cheung")
        self.assertEqual(seminar["physician"], "Dr. Xian Cheung")
        self.assertIn("ACAP", seminar["partners"])

    def test_proposes_an_iso_first_name(self):
        self.assertTrue(self.by_title("CAS Award Gala")["proposed"].startswith("2023-06-10 "))

    def test_includes_empty_event_folders_with_zero_photos(self):
        empty = self.by_title("David Zhuang")
        self.assertEqual(empty["photos"], 0)

    def test_ids_are_unique_and_slug_like(self):
        for e in self.events:
            self.assertRegex(e["id"], r"^[a-z0-9\-]+$")

    def test_sorted_by_date(self):
        dated = [e["iso"] for e in self.events if e["iso"]]
        self.assertEqual(dated, sorted(dated))

    def test_excludes_the_signage_folders_by_default(self):
        tops = {e["top"] for e in self.events}
        self.assertEqual(tops, {"Event Photos"})
        titles = " ".join(e["title"] for e in self.events)
        self.assertNotIn("Chinatown", titles)
        self.assertNotIn("Brooklyn", titles)

    def test_signage_folders_appear_when_tops_is_widened(self):
        rows = list(scan.walk(self.archive_root))
        everything = eventdata.collect_events(rows, tops=None)
        self.assertIn("_Completed Installation Photos",
                      {e["top"] for e in everything})
