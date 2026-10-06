# tools/tests/test_naming.py
import unittest

from tools import naming


class TestParseDate(unittest.TestCase):
    def check(self, name, expected_iso, year_hint=None):
        got = naming.parse_date(name, year_hint)
        self.assertIsNotNone(got, "failed to parse %r" % name)
        self.assertEqual(got["iso"], expected_iso, name)

    def test_mmdd_with_year_from_parent_folder(self):
        self.check("0512 Blood Pressure Seminar Flushing", "2022-05-12", 2022)
        self.check("1016 Breast Cancer Walk", "2022-10-16", 2022)

    def test_mmddyyyy_run_together(self):
        self.check("06102023 CAS Award Gala", "2023-06-10")
        self.check("10182023 Bay ST Grand Opening", "2023-10-18")

    def test_yymmdd(self):
        self.check("231113 Centerlight Health Fair", "2023-11-13")

    def test_dotted_two_digit_year(self):
        self.check("11.23.23 Centerlight Health Fair", "2023-11-23")
        self.check("5.8.25 Rendr Flushing STEB Grand Opening", "2025-05-08")

    def test_dotted_four_digit_year(self):
        self.check("3.27.2026 - Dr. Daniel Yeoun's Colorectal Cancer Seminar", "2026-03-27")

    def test_dotted_no_year_uses_hint(self):
        self.check("3.29 Dr. David Zhuang Health Talk", "2025-03-29", 2025)
        self.check("12.12 Dr. Xian Cheung ACAP Heath Seminar", "2025-12-12", 2025)

    def test_hyphenated_date_at_the_end(self):
        self.check("Provider Holiday Party 12-16-2023", "2023-12-16")

    def test_trailing_underscore_date(self):
        self.check("Flushing Basement Grand Opening_05082025", "2025-05-08")

    def test_stray_space_inside_the_date(self):
        self.check("UHC Golf Outing 5 .7", "2025-05-07", 2025)

    def test_month_name_and_year(self):
        self.check("Chinatown Open House with UHC_Mar2025", "2025-03-01")

    def test_returns_none_when_there_is_no_date(self):
        self.assertIsNone(naming.parse_date("Lunar New Year 2024", None))
        self.assertIsNone(naming.parse_date("Brain Health Day at CCBA", None))

    def test_rejects_impossible_dates(self):
        self.assertIsNone(naming.parse_date("9999 Nonsense", None))
        self.assertIsNone(naming.parse_date("1332 Bad Month", 2022))


class TestTitlesAndNames(unittest.TestCase):
    def test_clean_title_drops_the_date_token(self):
        self.assertEqual(
            naming.clean_title("0512 Blood Pressure Seminar Flushing"),
            "Blood Pressure Seminar Flushing",
        )

    def test_clean_title_drops_a_trailing_date_and_separator(self):
        self.assertEqual(
            naming.clean_title("Provider Holiday Party 12-16-2023"),
            "Provider Holiday Party",
        )

    def test_clean_title_drops_the_dash_after_a_2026_style_date(self):
        self.assertEqual(
            naming.clean_title("3.1.2026 - Chinatown LNY Parade"),
            "Chinatown LNY Parade",
        )

    def test_clean_title_collapses_double_spaces(self):
        self.assertEqual(naming.clean_title("UCA (Cultural)  Event"), "UCA (Cultural) Event")

    def test_proposed_name_is_iso_first(self):
        self.assertEqual(
            naming.proposed_name("0512 Blood Pressure Seminar Flushing", 2022),
            "2022-05-12 Blood Pressure Seminar Flushing",
        )

    def test_proposed_name_falls_back_to_year_only(self):
        self.assertEqual(
            naming.proposed_name("Lunar New Year 2024", 2024),
            "2024 Lunar New Year 2024",
        )

    def test_proposed_name_returns_input_when_nothing_is_known(self):
        self.assertEqual(naming.proposed_name("Mystery Folder", None), "Mystery Folder")

    def test_slugify(self):
        self.assertEqual(naming.slugify("Dr. Xian Cheung's Diabetes Seminar"),
                         "dr-xian-cheung-s-diabetes-seminar")


class TestConflicts(unittest.TestCase):
    def test_flags_one_title_carrying_two_dates(self):
        entries = [
            {"name": "11.23.23 Centerlight Health Fair", "iso": "2023-11-23", "path": "a"},
            {"name": "231113 Centerlight Health Fair", "iso": "2023-11-13", "path": "b"},
        ]
        conflicts = naming.find_conflicts(entries)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(sorted(conflicts[0]["dates"]), ["2023-11-13", "2023-11-23"])
        self.assertEqual(sorted(conflicts[0]["paths"]), ["a", "b"])

    def test_quiet_when_dates_agree(self):
        entries = [
            {"name": "231113 Centerlight Health Fair", "iso": "2023-11-13", "path": "a"},
            {"name": "11.13.23 Centerlight Health Fair", "iso": "2023-11-13", "path": "b"},
        ]
        self.assertEqual(naming.find_conflicts(entries), [])
