import os
import shutil
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

    def test_bare_month_container_is_not_an_empty_event(self):
        empty_events = eventdata.find_empty_event_dirs(self.archive_root)
        months = [e for e in empty_events if e[-1] == "October Event"]
        self.assertEqual(months, [])
        titles = " ".join(e["title"] for e in self.events)
        self.assertNotIn("October Event", titles)

    def test_id_is_stable_whether_or_not_a_catchall_mirror_is_present(self):
        # "0512 Blood Pressure Seminar Flushing" has a byte-identical mirror
        # under the "2022" catch-all folder (fixtures.CATCHALLS). Before a
        # cleanup removes that mirror, both records exist and compete for
        # the same base id; after, only the real event remains. The id the
        # real event gets must not depend on which of those two states the
        # archive is in -- otherwise a selection.json exported before a
        # cleanup silently stops resolving after one (see I2).
        with_mirror = self.by_title("Blood Pressure Seminar")
        self.assertFalse(with_mirror["catchall"])
        id_with_mirror = with_mirror["id"]

        mirror_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                                  "2022", "0512 Blood Pressure Seminar Flushing")
        self.assertTrue(os.path.isdir(mirror_dir))
        shutil.rmtree(mirror_dir)

        events_without_mirror = eventdata.collect_events(
            list(scan.walk(self.archive_root)),
            extra_dirs=eventdata.find_empty_event_dirs(self.archive_root),
        )
        without_mirror = next(e for e in events_without_mirror
                              if "Blood Pressure Seminar" in e["title"])
        self.assertEqual(without_mirror["id"], id_with_mirror)

    def test_nested_empty_event_two_levels_deep_is_still_an_event(self):
        empty_events = eventdata.find_empty_event_dirs(self.archive_root)
        matches = [e for e in empty_events
                  if "Bensonhurst" in e[-1]]
        self.assertEqual(len(matches), 1)
        nested = self.by_title("Bensonhurst")
        self.assertEqual(nested["photos"], 0)


class TestFindEmptyMonthDirs(fixtures.ArchiveFixture, unittest.TestCase):
    def test_surfaces_the_bare_month_container(self):
        months = eventdata.find_empty_month_dirs(self.archive_root)
        self.assertEqual(len(months), 1)
        rel, top, year, month = months[0]
        self.assertEqual(top, "Event Photos")
        self.assertEqual(year, "2026 Event")
        self.assertEqual(month, "October Event")

    def test_does_not_include_the_nested_empty_event(self):
        months = eventdata.find_empty_month_dirs(self.archive_root)
        names = [m[-1] for m in months]
        self.assertNotIn("4.2.2026 - HCS Q2 Birthday Party- Bensonhurst", names)
