import json
import os
import unittest

from tools import verify
from tools.tests import fixtures


def write_repo(root, data, files, html=""):
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    os.makedirs(os.path.join(root, "assets", "events", "thumbs"), exist_ok=True)
    with open(os.path.join(root, "data", "events.js"), "w") as fh:
        fh.write("window.GALLERY_DATA = %s;\n" % json.dumps(data))
    for rel, size in files:
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"\xff\xd8" + b"\x00" * max(size - 2, 0))
    with open(os.path.join(root, "index.html"), "w") as fh:
        fh.write(html or "<html><body></body></html>")


ONE_EVENT = {
    "events": [{
        "id": "e1", "date": "2026-06-09", "year": "2026", "title": "T",
        "category": "seminar", "category_label": "Health Seminars",
        "physician": "", "partners": [], "featured": True,
        "photos": [{"src": "assets/events/e1-001.jpg",
                    "thumb": "assets/events/thumbs/e1-001.jpg",
                    "w": 1400, "h": 933, "caption": "c", "featured": True}],
    }]
}


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.root = fixtures.make_tempdir()

    def tearDown(self):
        fixtures.cleanup(self.root)

    def results(self):
        return {r["check"]: r for r in verify.check(self.root)}

    def test_passes_a_consistent_repo(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ])
        for name, result in self.results().items():
            self.assertTrue(result["ok"], "%s: %s" % (name, result["detail"]))

    def test_flags_a_referenced_file_that_is_missing(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ])
        self.assertFalse(self.results()["every referenced file exists"]["ok"])

    def test_flags_an_orphan_file_nothing_references(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
            ("assets/events/orphan.jpg", 10 * 1024),
        ])
        self.assertFalse(self.results()["every asset is referenced"]["ok"])

    def test_flags_a_file_over_the_size_cap(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 600 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ])
        self.assertFalse(self.results()["no file over 500 KB"]["ok"])

    def test_flags_a_banned_format_in_assets(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
            ("assets/events/leftover.heic", 1024),
        ])
        self.assertFalse(self.results()["no web-hostile formats in assets"]["ok"])

    def test_flags_an_img_src_in_html_with_no_file(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ], html='<img src="assets/rebrand/ghost-before.jpg" alt="x">')
        self.assertFalse(self.results()["no dead img src in html"]["ok"])

    def test_ignores_remote_and_data_uris_in_html(self):
        write_repo(self.root, ONE_EVENT, [
            ("assets/events/e1-001.jpg", 200 * 1024),
            ("assets/events/thumbs/e1-001.jpg", 50 * 1024),
        ], html='<img src="https://example.com/a.png"><img src="data:image/gif;base64,R0lGOD">')
        self.assertTrue(self.results()["no dead img src in html"]["ok"])

    def test_load_gallery_data_parses_the_js_assignment(self):
        write_repo(self.root, ONE_EVENT, [])
        data = verify.load_gallery_data(os.path.join(self.root, "data", "events.js"))
        self.assertEqual(len(data["events"]), 1)
