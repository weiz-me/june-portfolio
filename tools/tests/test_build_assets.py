import json
import os
import re
import unittest
from unittest import mock

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

        with mock.patch("tools.build_assets.images.web",
                        wraps=build_assets.images.web) as spy_web:
            result = self.build()
        called_with = [call.args[0] for call in spy_web.call_args_list]
        self.assertNotIn(bogus_abs, called_with)

        self.assertEqual(result["photos"], 3)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIn("mov", result["skipped"][0]["why"])
        published = set(os.listdir(self.assets))
        self.assertNotIn("clip.mov", published)
        for name in published:
            if name == "thumbs":
                continue
            self.assertTrue(name.endswith(".jpg"))

    def test_republishing_a_smaller_selection_removes_stale_files(self):
        """Files are named <event_id>-NNN.jpg. Re-running build() with a
        smaller selection for an event must not leave the old
        higher-numbered files behind: Task 15's verifier checks assets in
        both directions (referenced files exist, and published files are
        referenced), so an orphan left over from a previous, larger
        selection fails that check far from its actual cause."""
        event = self.write_selection("Rendr Dinner")  # 3 photos
        self.build()
        full_before = set(os.listdir(self.assets)) - {"thumbs"}
        thumb_before = set(os.listdir(os.path.join(self.assets, "thumbs")))
        self.assertEqual(len(full_before), 3)
        self.assertEqual(len(thumb_before), 3)

        # Shrink the selection to a single photo from the same event.
        photos = [{"event_id": event["id"], "rel": event["rows"][0]["rel"],
                   "caption": ""}]
        with open(self.selection, "w") as fh:
            json.dump({"photos": photos}, fh)
        self.build()

        full_after = set(os.listdir(self.assets)) - {"thumbs"}
        thumb_after = set(os.listdir(os.path.join(self.assets, "thumbs")))
        self.assertEqual(len(full_after), 1)
        self.assertEqual(len(thumb_after), 1)
        gone = full_before - full_after
        self.assertEqual(len(gone), 2)
        # The same stale names must be gone from both the full-size and
        # thumbnail directories, not just miscounted.
        self.assertEqual(thumb_before - thumb_after, gone)

    def test_republish_cleanup_never_touches_files_outside_its_own_dirs(self):
        """_prune_stale must be scoped to assets_dir/thumbs_dir only -- a
        stray file sitting directly in assets_dir that was never produced
        by this tool (e.g. a sibling asset dropped there by hand) is still
        fair game per the "published set is authoritative" rule, but
        anything outside assets_dir entirely (a sibling directory) must
        never be touched."""
        self.write_selection("Rendr Dinner")
        sibling = os.path.join(os.path.dirname(self.assets), "rebrand")
        os.makedirs(sibling, exist_ok=True)
        untouched = os.path.join(sibling, "keep-me.jpg")
        with open(untouched, "w") as fh:
            fh.write("not touched")
        self.build()
        self.assertTrue(os.path.exists(untouched))

    def test_featured_set_spreads_across_events_capped_per_event(self):
        """A single uncapped counter walked in event order could let one
        early, heavily-selected event supply the entire featured strip.
        With three events of differing photo counts, the featured set must
        draw from all three and no event may contribute more than 2."""
        seminar = next(e for e in self.events if "Blood Pressure Seminar" in e["title"])
        gala = next(e for e in self.events if "CAS Award Gala" in e["title"])
        dinner = next(e for e in self.events if "Rendr Dinner" in e["title"])
        self.assertEqual(dinner["category"], "internal")
        self.assertNotEqual(seminar["category"], "internal")
        self.assertNotEqual(gala["category"], "internal")

        photos = []
        for event in (seminar, gala, dinner):
            for row in event["rows"]:
                photos.append({"event_id": event["id"], "rel": row["rel"],
                               "caption": ""})
        with open(self.selection, "w") as fh:
            json.dump({"photos": photos}, fh)

        result = build_assets.build(self.archive_root, self.selection,
                                    self.assets, self.data, featured=5)

        counts = {}
        for out_event in result["data"]["events"]:
            counts[out_event["id"]] = sum(
                1 for p in out_event["photos"] if p["featured"])

        self.assertEqual(sum(counts.values()), 5)
        self.assertTrue(all(c <= 2 for c in counts.values()))
        self.assertEqual(len([c for c in counts.values() if c > 0]), 3)
        # The internal event (fewer public photos available) only fills
        # the gap left by the two public events, never crowds them out.
        self.assertEqual(counts[dinner["id"]], 1)

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
