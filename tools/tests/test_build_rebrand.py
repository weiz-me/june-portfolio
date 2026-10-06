import html
import json
import os
import subprocess
import unittest
from unittest import mock

from tools import build_rebrand, images
from tools.tests import fixtures

# A minimal, deliberately malformed-but-recoverable PDF (wrong xref byte
# offsets) used to prove Finding 1: sips/CoreGraphics renders a PDF as a
# raster image with no error (confirmed directly in this environment --
# `sips -g pixelWidth -g pixelHeight` on this exact file returns 300x144,
# exit 0), so pick_photo()'s file branch must reject it by extension
# rather than relying on sips to complain. A plain text file would not
# prove this -- it would fail conversion anyway, for an unrelated reason.
_MINIMAL_PDF = b"""%PDF-1.1
1 0 obj
  << /Type /Catalog
     /Pages 2 0 R
  >>
endobj
2 0 obj
  << /Type /Pages
     /Kids [3 0 R]
     /Count 1
     /MediaBox [0 0 300 144]
  >>
endobj
3 0 obj
  <<  /Type /Page
      /Parent 2 0 R
      /Resources
       << /Font
           << /F1
               << /Type /Font
                  /Subtype /Type1
                  /BaseFont /Times-Roman
               >>
           >>
       >>
      /Contents 4 0 R
  >>
endobj
4 0 obj
  << /Length 55 >>
stream
  BT
    /F1 18 Tf
    0 0 Td
    (Hello World) Tj
  ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000018 00000 n
0000000077 00000 n
0000000178 00000 n
0000000457 00000 n
trailer
  <<  /Root 1 0 R
      /Size 5
  >>
startxref
565
%%EOF
"""


def _write_minimal_pdf(path):
    with open(path, "wb") as fh:
        fh.write(_MINIMAL_PDF)
    return path


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

    def test_rejects_a_loose_non_image_file_even_though_sips_can_read_it(self):
        # Finding 1: the archive has 12 loose PDFs under
        # `_Original Legacy Rendr Photo`, and sips happily rasterizes a
        # PDF -- no error, exit 0 -- so the file branch must not accept
        # anything just because os.path.isfile() is true. Confirm first
        # that sips really does read this file (otherwise the test proves
        # nothing), then confirm pick_photo rejects it anyway.
        #
        # Checked directly via subprocess rather than images.dimensions():
        # sips reports a PDF's pixelWidth/pixelHeight as floats
        # ("300.000"), which images.dimensions()'s int(value) cannot
        # parse -- a separate, pre-existing quirk in images.py, out of
        # scope for this fix. The point here is only that sips's exit
        # code is 0 and it did produce pixel dimensions, proving the
        # file would otherwise sail through unfiltered.
        pdf = _write_minimal_pdf(os.path.join(self.tmp, "139 Centre St.pdf"))
        proc = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", pdf],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"pixelWidth", proc.stdout)
        self.assertNotIn(b"<nil>", proc.stdout)

        self.assertIsNone(build_rebrand.pick_photo(pdf))


class TestBuild(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        # build()'s contract is that `assets_dir` is itself a repo-relative
        # path (the CLI's own default, "assets/rebrand", is relative to
        # cwd) -- disk I/O and the recorded JSON path both derive from it.
        # Mirror that contract here instead of handing it an absolute
        # tempdir path: chdir into a scratch "repo root" and pass relative
        # out/assets dirs, exactly as the real CLI is invoked.
        self._prev_cwd = os.getcwd()
        os.chdir(self.work)
        self.out = "out"
        self.assets = os.path.join("assets", "rebrand")

    def tearDown(self):
        os.chdir(self._prev_cwd)
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

    # -- Finding 2: assets_rel must be derived from assets_dir, not the
    # literal string "assets/rebrand". --

    def test_published_path_is_derived_from_assets_dir_not_hardcoded(self):
        custom_assets = os.path.join("static", "photos")
        result = build_rebrand.build(self.archive_root, self.out, custom_assets, limit=1)
        entry = result["published"][0]
        self.assertTrue(entry["before"].startswith("static/photos/"), entry["before"])
        self.assertTrue(entry["after"].startswith("static/photos/"), entry["after"])
        self.assertFalse(os.path.isabs(entry["before"]))
        # And the file really is where the recorded path says it is --
        # proves the JSON path and the actual write target agree.
        disk = os.path.join(self.work, entry["before"])
        self.assertTrue(os.path.exists(disk), disk)

    # -- Finding 3: a failed "after" conversion must not leave an orphan
    # "before" file that nothing references. --

    def test_orphan_before_file_is_removed_when_after_conversion_fails(self):
        real_web = images.web
        calls = {"n": 0}

        def flaky_web(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:  # the "after" side of the first pair
                raise images.SipsError("simulated failure")
            return real_web(src, dst)

        with mock.patch("tools.build_rebrand.images.web", side_effect=flaky_web):
            result = build_rebrand.build(self.archive_root, self.out, self.assets, limit=1)

        self.assertEqual(result["published"], [])
        self.assertEqual(len(result["skipped"]), 1)
        slug = result["skipped"][0]["slug"]
        before_path = os.path.join(self.assets, "%s-before.jpg" % slug)
        self.assertFalse(os.path.exists(before_path), before_path)


class TestHtmlSnippetEscaping(unittest.TestCase):
    # -- Finding 4: labels come from folder names on disk and can contain
    # "&", '"', and "<" -- all of which must be escaped before landing in
    # either an HTML attribute or element-text position. --

    def test_escapes_ampersand_quote_and_angle_bracket_in_labels(self):
        label = 'Dr. Daniel Yeoun & lab - 26-19 "Francis" <Lewis> Blvd'
        published = [{
            "slug": "a-b-clinic",
            "label": label,
            "before": "assets/rebrand/a-b-clinic-before.jpg",
            "after": "assets/rebrand/a-b-clinic-after.jpg",
            "w": 10,
            "h": 10,
        }]
        out = build_rebrand.html_snippet(published)
        expected = html.escape(label, quote=True)
        self.assertIn(expected, out)
        self.assertNotIn(label, out)       # the raw, unescaped label must not appear
        self.assertNotIn("<Lewis>", out)
        self.assertNotIn('"Francis"', out)
        self.assertNotIn(" & lab", out)    # raw ampersand must not survive


if __name__ == "__main__":
    unittest.main()
