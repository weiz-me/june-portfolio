import json
import os
import unittest

from tools import build_rebrand
from tools.tests import fixtures


class TestSlugify(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(build_rebrand.slugify("2251 86th St"), "2251-86th-st")

    def test_collapses_punctuation_and_runs(self):
        self.assertEqual(build_rebrand.slugify("Dr. Hall  --  94 Bowery!"),
                         "dr-hall-94-bowery")

    def test_never_starts_or_ends_with_a_hyphen(self):
        slug = build_rebrand.slugify("  -- 94 Bowery -- ")
        self.assertFalse(slug.startswith("-"))
        self.assertFalse(slug.endswith("-"))


class TestPickPhoto(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_picks_the_largest_image(self):
        small = fixtures.make_seed_image(os.path.join(self.tmp, "small.jpg"), "jpg")
        big = os.path.join(self.tmp, "big.jpg")
        with open(small, "rb") as fh:
            data = fh.read()
        with open(big, "wb") as fh:
            fh.write(data + b"\x00" * 5000)
        self.assertEqual(build_rebrand.pick_photo(self.tmp), big)

    def test_ignores_non_images_and_dotfiles(self):
        with open(os.path.join(self.tmp, ".DS_Store"), "w") as fh:
            fh.write("x" * 9999)
        with open(os.path.join(self.tmp, "notes.txt"), "w") as fh:
            fh.write("x" * 9999)
        jpg = fixtures.make_seed_image(os.path.join(self.tmp, "a.jpg"), "jpg")
        self.assertEqual(build_rebrand.pick_photo(self.tmp), jpg)

    def test_returns_none_for_an_empty_folder(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        self.assertIsNone(build_rebrand.pick_photo(empty))

    def test_a_loose_file_path_is_used_directly(self):
        # Some real-archive "before" entries are loose files, not folders
        # (_Original Legacy Rendr Photo). pick_photo must accept a file
        # path and hand it back unchanged rather than trying to list it.
        jpg = fixtures.make_seed_image(os.path.join(self.tmp, "loose.jpg"), "jpg")
        self.assertEqual(build_rebrand.pick_photo(jpg), jpg)


class TestBuild(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        self.out = os.path.join(self.work, "out")
        self.assets = os.path.join(self.work, "assets", "rebrand")

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def test_writes_a_json_file_with_every_matched_pair(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=2)
        path = os.path.join(self.out, "rebrand-pairs.json")
        with open(path) as fh:
            data = json.load(fh)
        self.assertEqual(len(data["pairs"]), 3)      # fixture plants 3 matches
        self.assertEqual(len(result["published"]), 2)  # limit honored

    def test_publishes_two_jpegs_per_pair(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=2)
        for entry in result["published"]:
            for key in ("before", "after"):
                disk = os.path.join(self.work, entry[key])
                self.assertTrue(os.path.exists(disk), entry[key])
                with open(disk, "rb") as fh:
                    self.assertEqual(fh.read(2), b"\xff\xd8")

    def test_published_paths_are_repo_relative(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=1)
        entry = result["published"][0]
        self.assertTrue(entry["before"].startswith("assets/rebrand/"))
        self.assertFalse(os.path.isabs(entry["before"]))

    def test_records_pixel_dimensions(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=1)
        entry = result["published"][0]
        self.assertGreater(entry["w"], 0)
        self.assertGreater(entry["h"], 0)

    def test_does_not_modify_the_archive(self):
        before = sorted(
            os.path.join(dp, f)
            for dp, dn, fn in os.walk(self.archive_root) for f in fn
        )
        build_rebrand.build(self.archive_root, self.out, self.assets, limit=3)
        after = sorted(
            os.path.join(dp, f)
            for dp, dn, fn in os.walk(self.archive_root) for f in fn
        )
        self.assertEqual(before, after)

    def test_snippet_contains_one_pair_block_per_published_pair(self):
        result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=2)
        html = build_rebrand.html_snippet(result["published"])
        self.assertEqual(html.count("data-ba-pair"), 2)
        self.assertIn('class="ba-pair active"', html)
        self.assertIn("data-slot=", html)   # keeps the placeholder fallback

    # -- `only` addition: lets a human pick which pairs ship, since the
    # captions name real former practices. --

    def test_only_selects_exactly_the_named_pairs(self):
        all_pairs = build_rebrand.build(self.archive_root, self.out, self.assets, limit=3)
        labels = sorted(p["label"] for p in all_pairs["pairs"])
        self.assertEqual(len(labels), 3)
        wanted_slug = build_rebrand.slugify(labels[0])
        result = build_rebrand.build(
            self.archive_root, self.out, self.assets, only=[wanted_slug]
        )
        self.assertEqual(len(result["published"]), 1)
        self.assertEqual(result["published"][0]["slug"], wanted_slug)

    def test_only_honors_the_given_order(self):
        all_pairs = build_rebrand.build(self.archive_root, self.out, self.assets, limit=3)
        slugs = [build_rebrand.slugify(p["label"]) for p in all_pairs["pairs"]]
        reversed_slugs = list(reversed(slugs))
        result = build_rebrand.build(
            self.archive_root, self.out, self.assets, only=reversed_slugs
        )
        published_slugs = [p["slug"] for p in result["published"]]
        self.assertEqual(published_slugs, reversed_slugs)

    def test_only_with_an_unknown_slug_lands_in_skipped(self):
        result = build_rebrand.build(
            self.archive_root, self.out, self.assets, only=["not-a-real-slug"]
        )
        self.assertEqual(len(result["published"]), 0)
        skipped_slugs = [s.get("slug") for s in result["skipped"]]
        self.assertIn("not-a-real-slug", skipped_slugs)
        reasons = [s["why"] for s in result["skipped"] if s.get("slug") == "not-a-real-slug"]
        self.assertTrue(reasons and "no pair" in reasons[0].lower())

    def test_only_ignores_limit_when_non_empty(self):
        result = build_rebrand.build(
            self.archive_root, self.out, self.assets, limit=1,
            only=["not-a-real-slug"],
        )
        # limit=1 would normally cap published at 1, but only=[] with one
        # unknown slug means zero publishable pairs regardless of limit.
        self.assertEqual(len(result["published"]), 0)

    def test_empty_only_list_falls_back_to_limit_behavior(self):
        result = build_rebrand.build(
            self.archive_root, self.out, self.assets, limit=2, only=[]
        )
        self.assertEqual(len(result["published"]), 2)


if __name__ == "__main__":
    unittest.main()
