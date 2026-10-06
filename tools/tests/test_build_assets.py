import json
import os
import re
import unittest

from tools import build_assets, eventdata, scan
from tools.tests import fixtures


class TestBuildAssets(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        self.assets = os.path.join(self.work, "assets", "events")
        self.data = os.path.join(self.work, "data", "events.js")
        self.events = eventdata.collect_events(list(scan.walk(self.archive_root)))
        self.selection = os.path.join(self.work, "selection.json")

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def write_selection(self, needle, captions=True):
        event = next(e for e in self.events if needle in e["title"])
        photos = [{"event_id": event["id"], "rel": r["rel"],
                   "caption": "Caption %d" % i if captions else ""}
                  for i, r in enumerate(event["rows"], start=1)]
        with open(self.selection, "w") as fh:
            json.dump({"photos": photos}, fh)
        return event

    def build(self):
        return build_assets.build(self.archive_root, self.selection,
                                  self.assets, self.data, featured=2)

    def test_publishes_a_web_image_and_a_thumbnail_per_photo(self):
        event = self.write_selection("Rendr Dinner")
        result = self.build()
        self.assertEqual(result["photos"], 3)
        self.assertEqual(len(os.listdir(self.assets)) - 1, 3)   # minus thumbs/
        self.assertEqual(len(os.listdir(os.path.join(self.assets, "thumbs"))), 3)

    def test_writes_a_loadable_js_data_file(self):
        self.write_selection("Rendr Dinner")
        self.build()
        with open(self.data) as fh:
            text = fh.read()
        self.assertTrue(text.startswith("window.GALLERY_DATA = "))
        self.assertTrue(text.rstrip().endswith(";"))
        payload = json.loads(text[len("window.GALLERY_DATA = "):].rstrip().rstrip(";"))
        self.assertEqual(len(payload["events"]), 1)

    def test_records_real_pixel_dimensions(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        photo = result["data"]["events"][0]["photos"][0]
        self.assertGreater(photo["w"], 0)
        self.assertGreater(photo["h"], 0)

    def test_paths_are_repo_relative_and_forward_slashed(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        photo = result["data"]["events"][0]["photos"][0]
        self.assertTrue(photo["src"].startswith("assets/events/"))
        self.assertTrue(photo["thumb"].startswith("assets/events/thumbs/"))
        self.assertNotIn("\\", photo["src"])

    def test_keeps_the_caption_from_the_selection(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        self.assertEqual(result["data"]["events"][0]["photos"][0]["caption"],
                         "Caption 1")

    def test_falls_back_to_the_event_title_when_caption_is_blank(self):
        event = self.write_selection("Rendr Dinner", captions=False)
        result = self.build()
        self.assertEqual(result["data"]["events"][0]["photos"][0]["caption"],
                         event["title"])

    def test_carries_event_metadata_into_the_payload(self):
        self.write_selection("Blood Pressure Seminar")
        result = self.build()
        event = result["data"]["events"][0]
        for key in ("id", "date", "title", "category", "category_label",
                    "physician", "partners", "featured", "photos"):
            self.assertIn(key, event)

    def test_marks_only_the_first_n_photos_as_featured(self):
        self.write_selection("Rendr Dinner")
        result = self.build()
        featured = [p for e in result["data"]["events"] for p in e["photos"]
                    if p["featured"]]
        self.assertEqual(len(featured), 2)   # featured=2

    def test_converts_heic_selections_to_jpeg(self):
        self.write_selection("Centerlight")
        result = self.build()
        self.assertEqual(result["skipped"], [])
        for name in os.listdir(self.assets):
            if name == "thumbs":
                continue
            self.assertTrue(name.endswith(".jpg"))

    def test_every_published_file_stays_under_the_size_cap(self):
        self.write_selection("Rendr Dinner")
        self.build()
        for root, dirs, files in os.walk(self.assets):
            for name in files:
                self.assertLess(os.path.getsize(os.path.join(root, name)), 500 * 1024)

    def test_ignores_selection_entries_whose_event_is_unknown(self):
        with open(self.selection, "w") as fh:
            json.dump({"photos": [{"event_id": "nope", "rel": "x.jpg", "caption": ""}]}, fh)
        result = self.build()
        self.assertEqual(result["photos"], 0)
        self.assertEqual(len(result["skipped"]), 1)

    # --- Extra coverage beyond the brief (see task-13-report.md) ---

    def test_skips_non_publishable_extensions_named_in_the_selection(self):
        """Event folders contain .mov/.tif/.zip/.mp4/.dng alongside photos.
        A selection could name one of those; it must be recorded in
        `skipped` with a reason naming the extension and never reach
        images.web/images.thumb (which would raise or, worse, silently
        convert something nobody meant to publish)."""
        event = self.write_selection("Rendr Dinner")
        bogus_rel = os.path.join(os.path.dirname(event["rows"][0]["rel"]), "clip.mov")
        bogus_abs = os.path.join(self.archive_root, bogus_rel)
        with open(bogus_abs, "wb") as fh:
            fh.write(b"not a real quicktime file")
        with open(self.selection) as fh:
            payload = json.load(fh)
        payload["photos"].append({"event_id": event["id"], "rel": bogus_rel,
                                  "caption": ""})
        with open(self.selection, "w") as fh:
            json.dump(payload, fh)

        result = self.build()

        self.assertEqual(result["photos"], 3)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIn("mov", result["skipped"][0]["why"])
        published = set(os.listdir(self.assets))
        self.assertNotIn("clip.mov", published)
        for name in published:
            if name == "thumbs":
                continue
            self.assertTrue(name.endswith(".jpg"))

    def test_empty_selection_still_produces_a_loadable_data_file(self):
        """data/events.js is a placeholder the gallery page already loads
        via <script>. An empty selection must still overwrite it with a
        valid, loadable file (`{"events": []}`), not a broken one."""
        with open(self.selection, "w") as fh:
            json.dump({"photos": []}, fh)
        result = self.build()
        self.assertEqual(result["photos"], 0)
        self.assertEqual(result["events"], 0)
        with open(self.data) as fh:
            text = fh.read()
        self.assertTrue(text.startswith("window.GALLERY_DATA = "))
        payload = json.loads(text[len("window.GALLERY_DATA = "):].rstrip().rstrip(";"))
        self.assertEqual(payload["events"], [])

    def test_json_path_is_opt_in_and_not_written_by_default(self):
        """json_path must default to None: an earlier draft of this brief
        defaulted it to the cwd-relative 'tools/out/events.json', which made
        the test suite write into the real repo. build() must never write
        that file unless the caller passes json_path explicitly."""
        self.write_selection("Rendr Dinner")
        cwd = os.getcwd()
        os.chdir(self.work)
        try:
            build_assets.build(self.archive_root, self.selection,
                               self.assets, self.data, featured=2)
        finally:
            os.chdir(cwd)
        self.assertFalse(os.path.exists(os.path.join(self.work, "tools")))

        json_path = os.path.join(self.work, "out", "events.json")
        build_assets.build(self.archive_root, self.selection, self.assets,
                           self.data, featured=2, json_path=json_path)
        self.assertTrue(os.path.exists(json_path))


if __name__ == "__main__":
    unittest.main()
