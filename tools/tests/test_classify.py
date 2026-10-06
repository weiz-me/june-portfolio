import unittest

from tools import classify


class TestCategory(unittest.TestCase):
    def check(self, title, expected):
        self.assertEqual(classify.category(title), expected, title)

    def test_seminars(self):
        self.check("Dr. Xian Cheung's Diabetes Focus on Diet Seminar with Wellcare & CPC", "seminar")
        self.check("Dr. David Zhuang Health Talk", "seminar")
        self.check("Podiatry Health Seminar at CCBA", "seminar")

    def test_fairs(self):
        self.check("VNS Health Fair & LNY Celebration", "fair")
        self.check("CCPH Wellness Day 2026", "fair")
        self.check("WJ Health Expo", "fair")
        self.check("Spring Into Health & Community Resource Fair", "fair")

    def test_openings(self):
        self.check("Bay ST Grand Opening", "opening")
        self.check("Rendr Flushing Open House with UHC", "opening")
        self.check("Queens Supersite Open House with UHC", "opening")

    def test_galas_and_awards(self):
        self.check("CAS Award Gala", "gala")
        self.check("HCS 26th Anniversary Gala", "gala")
        self.check("Signing Ceremony", "gala")

    def test_sponsorships(self):
        self.check("Breast Cancer Walk", "sponsorship")
        self.check("Swim Across America", "sponsorship")
        self.check("UHC Golf Outing", "sponsorship")

    def test_cultural(self):
        self.check("Chinatown LNY Parade", "cultural")
        self.check("SI 2025 Asian Heritage Celebration", "cultural")
        self.check("CPC Mother & Father's day celebration", "cultural")

    def test_internal_wins_over_everything_else(self):
        # These read like celebrations or dinners but are staff-only.
        self.check("Rendr Dinner", "internal")
        self.check("Team Building Event", "internal")
        self.check("Provider Holiday Party", "internal")
        self.check("PCP End-of-Summer provider dinner", "internal")
        self.check("2025 Physician Shareholder's End-of-Summer Celebration", "internal")
        self.check("End_of _Year Physician celebration 2024", "internal")

    def test_unknown_falls_back_to_other(self):
        self.check("Mystery Folder", "other")

    def test_internal_is_excluded_from_publishable(self):
        self.assertNotIn("internal", classify.PUBLISHABLE_CATEGORIES)
        self.assertIn("seminar", classify.PUBLISHABLE_CATEGORIES)

    def test_every_category_has_a_label(self):
        for cid in classify.CATEGORIES:
            self.assertIn(cid, classify.LABELS)


class TestPartners(unittest.TestCase):
    def test_canonicalizes_payer_aliases(self):
        self.assertEqual(classify.partners("Seminar with UHC & HCS"),
                         ["HCS", "UnitedHealthcare"])
        self.assertEqual(classify.partners("Open House with UnitedHealthcare"),
                         ["UnitedHealthcare"])

    def test_finds_community_partners(self):
        self.assertEqual(
            classify.partners("Dr. Xian Cheung's Diabetes Seminar with Wellcare & CPC"),
            ["CPC", "WellCare"],
        )

    def test_matches_whole_words_only(self):
        # "VNS" must not be found inside an unrelated word.
        self.assertEqual(classify.partners("TRANSVNSPORT event"), [])

    def test_returns_empty_when_no_partner_is_named(self):
        self.assertEqual(classify.partners("Team Building Event"), [])


class TestPhysician(unittest.TestCase):
    def test_finds_dr_prefix(self):
        self.assertEqual(classify.physician("Dr. Harry He Liver Disease Health Seminar"),
                         "Dr. Harry He")

    def test_finds_md_suffix(self):
        self.assertEqual(classify.physician("Hearing and Balance Health Seminar - Kuo Chih Yung, MD"),
                         "Kuo Chih Yung, MD")

    def test_strips_a_possessive(self):
        self.assertEqual(classify.physician("Dr. Brian Poon's Prevention Seminar"),
                         "Dr. Brian Poon")

    def test_returns_none_without_a_physician(self):
        self.assertIsNone(classify.physician("Chinatown LNY Parade"))
