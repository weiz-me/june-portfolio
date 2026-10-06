import json
import os
import unittest
from unittest import mock

from tools import eventdata, images, scan, thumbs
from tools.tests import fixtures


class TestThumbs(fixtures.ArchiveFixture, unittest.TestCase):
    def setUp(self):
        fixtures.ArchiveFixture.setUp(self)
        self.work = fixtures.make_tempdir()
        self.thumb_dir = os.path.join(self.work, "thumbs")
        self.html = os.path.join(self.work, "index.html")
        self.events = eventdata.collect_events(list(scan.walk(self.archive_root)))

    def tearDown(self):
        fixtures.ArchiveFixture.tearDown(self)
        fixtures.cleanup(self.work)

    def ids_for(self, *needles):
        # Exclude catch-all mirrors: collect_events() returns one record per
        # (top, year, event, catchall) group, so a non-catchall event that is
        # also byte-mirrored into a catch-all folder (as the fixture's
        # "1023 Rendr Dinner" deliberately is, to exercise dupes.py) produces
        # two distinct ids with the same title. Every production caller
        # (manifests.py) only ever hands build() ids for verified-unique
        # events -- the manifest never lists a verified catch-all mirror as
        # a row to tick -- so real event_ids passed to thumbs.build() never
        # include one. Matching that convention here, same as test_hydrate.py
        # does for this identical fixture quirk, rather than the brief's
        # original unfiltered version, which picked up both ids for "Rendr
        # Dinner" and inflated thumbs/events 2x.
        return [e["id"] for e in self.events
                if any(n in e["title"] for n in needles) and not e["catchall"]]

    def test_writes_one_thumbnail_per_photo(self):
        ids = self.ids_for("Rendr Dinner")
        result = thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        self.assertEqual(result["thumbs"], 3)
        self.assertEqual(len(os.listdir(self.thumb_dir)), 3)

    def test_thumbnails_are_small_jpegs(self):
        ids = self.ids_for("Rendr Dinner")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        for name in os.listdir(self.thumb_dir):
            path = os.path.join(self.thumb_dir, name)
            self.assertTrue(name.endswith(".jpg"))
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(2), b"\xff\xd8")

    def test_converts_heic_sources(self):
        ids = self.ids_for("Centerlight")
        result = thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        self.assertGreater(result["thumbs"], 0)
        self.assertEqual(result["skipped"], [])

    def test_html_embeds_absolute_source_paths_for_full_size_viewing(self):
        ids = self.ids_for("Rendr Dinner")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        with open(self.html) as fh:
            text = fh.read()
        self.assertIn(self.archive_root, text)

    def test_internal_events_are_collapsed_and_flagged(self):
        ids = self.ids_for("Rendr Dinner", "Blood Pressure Seminar")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        with open(self.html) as fh:
            text = fh.read()
        self.assertIn("<details", text)
        self.assertNotIn("<details open", text)
        self.assertIn("Internal / Provider", text)

    def test_html_carries_a_json_payload_the_picker_can_read(self):
        ids = self.ids_for("Rendr Dinner")
        thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        with open(self.html) as fh:
            text = fh.read()
        start = text.index('id="picker-data"')
        payload = text[text.index(">", start) + 1:text.index("</script>", start)]
        data = json.loads(payload)
        self.assertEqual(len(data["events"]), 1)
        self.assertIn("rel", data["events"][0]["photos"][0])

    def test_reports_unreadable_sources_instead_of_crashing(self):
        bad_dir = os.path.join(self.archive_root, "Event Photos", "2022 Events",
                               "9999 Broken Event")
        os.makedirs(bad_dir)
        with open(os.path.join(bad_dir, "broken.jpg"), "w") as fh:
            fh.write("not an image")
        events = eventdata.collect_events(list(scan.walk(self.archive_root)))
        ids = [e["id"] for e in events if "Broken Event" in e["title"]]
        result = thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)
        self.assertEqual(result["thumbs"], 0)
        self.assertEqual(len(result["skipped"]), 1)

    def test_build_honors_an_explicitly_passed_catchall_id(self):
        # build() sits downstream of a human's explicit pick (--events or a
        # ticked manifest row) and must not silently drop an event just
        # because collect_events() happened to flag it catchall=True.
        # Whether a catch-all folder is a verified duplicate is a question
        # for dupes.py/manifests.py to answer upstream, before an id ever
        # reaches here -- not one for build() to re-litigate.
        catchall_id = next(e["id"] for e in self.events
                           if "Rendr Dinner" in e["title"] and e["catchall"])
        result = thumbs.build(self.archive_root, [catchall_id], self.thumb_dir, self.html)
        self.assertEqual(result["events"], 1)
        self.assertEqual(result["thumbs"], 3)
        self.assertEqual(result["skipped"], [])

    def test_skips_non_image_extensions_without_reaching_images_thumb(self):
        # Real event folders hold .mov/.zip/.dng/.tif/.mp4 alongside photos.
        # These must be filtered out by extension before any sips call, so
        # a .zip reads as "not an image" rather than surfacing as a
        # conversion (SipsError) failure.
        event_dir = os.path.join(self.archive_root, "Event Photos",
                                  "2022 Events", "1023 Rendr Dinner")
        extras = {"clip.MOV": b"not a video really",
                  "archive.zip": b"PK\x03\x04fake",
                  "raw.dng": b"fake raw bytes"}
        for name, content in extras.items():
            with open(os.path.join(event_dir, name), "wb") as fh:
                fh.write(content)

        events = eventdata.collect_events(list(scan.walk(self.archive_root)))
        ids = [e["id"] for e in events
               if "Rendr Dinner" in e["title"] and not e["catchall"]]

        real_thumb = images.thumb
        calls = []

        def spy(src, dst):
            calls.append(src)
            return real_thumb(src, dst)

        with mock.patch("tools.thumbs.images.thumb", side_effect=spy):
            result = thumbs.build(self.archive_root, ids, self.thumb_dir, self.html)

        # Only the 3 real jpgs were ever handed to images.thumb().
        self.assertEqual(len(calls), 3)
        for src in calls:
            ext = src.rsplit(".", 1)[-1].lower()
            self.assertNotIn(ext, ("mov", "zip", "dng"))

        self.assertEqual(result["thumbs"], 3)
        skipped_names = sorted(os.path.basename(s["rel"]) for s in result["skipped"])
        self.assertEqual(skipped_names, ["archive.zip", "clip.MOV", "raw.dng"])
        for entry in result["skipped"]:
            self.assertIn(".%s" % entry["rel"].rsplit(".", 1)[-1].lower(), entry["why"])
            self.assertIn("not an image", entry["why"].lower())


if __name__ == "__main__":
    unittest.main()
