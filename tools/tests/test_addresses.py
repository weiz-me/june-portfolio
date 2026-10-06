import unittest

from tools import addresses
from tools.tests import fixtures


class TestNormalize(unittest.TestCase):
    def test_strips_a_leading_practice_name(self):
        self.assertEqual(addresses.normalize("Dr. Hall - 2251 86th St"), "2251 86th")

    def test_matches_the_same_address_written_two_ways(self):
        self.assertEqual(
            addresses.normalize("Zhengbo Huang, MD - 142-18 38th Ave"),
            addresses.normalize("Dr. Zhengbo Huang - 142-18 38th Ave"),
        )

    def test_ignores_hyphens_inside_the_house_number(self):
        self.assertEqual(addresses.normalize("136-20 38th St"), "13620 38th")

    def test_ignores_suite_and_floor_suffixes(self):
        self.assertEqual(
            addresses.normalize("Dr. Henry Chen - 128 Mott ST 308"),
            addresses.normalize("Oncology - 128 Mott St. Suite 309"),
        )

    def test_returns_none_without_an_address(self):
        self.assertIsNone(addresses.normalize("Lunar New Year 2024"))

    def test_handles_a_filename_with_an_extension_and_descriptor(self):
        self.assertEqual(
            addresses.normalize("7217 18th Ave - Logo.png"), "7217 18th"
        )

    def test_prefers_the_complete_address_before_an_unrecognized_trailing_dash(self):
        # The practice name here is number-first too ("136-20 38th St"
        # itself looks like a complete address), but what follows the
        # loose dash is not one of the known photo-descriptor words, so a
        # naive "always take the text after the dash" rule would wrongly
        # match on "2024 Renovation" instead.
        self.assertEqual(
            addresses.normalize("136-20 38th St - 2024 Renovation"), "13620 38th"
        )

    def test_prefers_the_address_when_the_practice_name_starts_with_the_same_number(self):
        # "833 Janlian Medical Group" is syntactically number-first too,
        # but it is not a complete address (nothing street-like follows
        # the house number), so the real address after the dash must win.
        self.assertEqual(
            addresses.normalize("833 Janlian Medical Group - 833 58th St"),
            "833 58th",
        )

    def test_finds_the_address_past_a_tight_dash_inside_the_practice_name(self):
        # The first dash of any kind is the tight one inside
        # "Imaging-Urgent"; the real separator is the loose dash before
        # "729".
        self.assertEqual(
            addresses.normalize("Medical Imaging-Urgent Care - 729 61st ST"),
            "729 61st",
        )

    def test_finds_the_address_past_a_typo_dash_with_no_surrounding_space(self):
        self.assertEqual(
            addresses.normalize("Dr. Chixin Fang-730 58th Street"), "730 58th"
        )


class TestLabel(unittest.TestCase):
    def test_label_does_not_leave_a_fragment_from_a_tight_dash(self):
        # Regression: _label used to strip only at the first dash of any
        # kind, so this real archive name produced the user-visible label
        # "Urgent Care - 729 61st ST" instead of just the address. _label
        # only inspects the basename, so a non-existent path is fine here.
        after_dir = (
            "/Event_photos/_Completed Installation Photos/"
            "Medical Imaging-Urgent Care - 729 61st ST"
        )
        self.assertEqual(addresses._label(after_dir), "729 61st ST")


class TestMatching(fixtures.ArchiveFixture, unittest.TestCase):
    def test_finds_the_three_planted_pairs(self):
        pairs = addresses.match_pairs(self.archive_root)
        found = sorted(p["address"] for p in pairs)
        self.assertEqual(found, ["14218 38th", "2251 86th", "94 bowery"])

    def test_excludes_before_only_and_after_only_locations(self):
        pairs = addresses.match_pairs(self.archive_root)
        joined = " ".join(p["before_dir"] + p["after_dir"] for p in pairs)
        self.assertNotIn("Nowhere", joined)
        self.assertNotIn("Elsewhere", joined)

    def test_each_pair_carries_both_sides_and_a_label(self):
        pair = addresses.match_pairs(self.archive_root)[0]
        for key in ("address", "before_dir", "after_dir", "label"):
            self.assertIn(key, pair)
            self.assertTrue(pair[key])

    def test_legacy_rendr_files_contribute_before_entries(self):
        before = addresses.collect_before(self.archive_root)
        self.assertIn("7217 18th", before)
