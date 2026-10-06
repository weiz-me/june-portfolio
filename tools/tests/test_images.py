import os
import unittest

from tools import images
from tools.tests import fixtures


class TestImages(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()
        self.jpg = fixtures.make_seed_image(os.path.join(self.tmp, "src.jpg"), "jpg")
        self.heic = fixtures.make_seed_image(os.path.join(self.tmp, "src.heic"), "heic")

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_dimensions_reads_real_pixels(self):
        self.assertEqual(images.dimensions(self.jpg), (64, 48))

    def test_to_jpeg_scales_the_long_edge_and_keeps_aspect(self):
        out = os.path.join(self.tmp, "out.jpg")
        got = images.to_jpeg(self.jpg, out, 32, 70)
        self.assertEqual(got["w"], 32)
        self.assertEqual(got["h"], 24)
        self.assertEqual(images.dimensions(out), (32, 24))
        self.assertEqual(got["bytes"], os.path.getsize(out))

    def test_never_upscales(self):
        # sips -Z on its own WOULD upscale this to 4000x3000; to_jpeg clamps.
        out = os.path.join(self.tmp, "big.jpg")
        got = images.to_jpeg(self.jpg, out, 4000, 70)
        self.assertEqual((got["w"], got["h"]), (64, 48))
        self.assertEqual(images.dimensions(out), (64, 48))

    def test_converts_heic_to_jpeg(self):
        out = os.path.join(self.tmp, "from_heic.jpg")
        images.to_jpeg(self.heic, out, 64, 70)
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(2), b"\xff\xd8")

    def test_creates_missing_parent_directories(self):
        out = os.path.join(self.tmp, "deep", "nested", "out.jpg")
        images.to_jpeg(self.jpg, out, 32, 70)
        self.assertTrue(os.path.exists(out))

    def test_raises_sipserror_with_stderr_on_bad_input(self):
        bad = os.path.join(self.tmp, "not-an-image.jpg")
        with open(bad, "w") as fh:
            fh.write("definitely not a jpeg")
        with self.assertRaises(images.SipsError):
            images.dimensions(bad)

    def test_web_and_thumb_use_the_documented_constants(self):
        self.assertEqual((images.WEB_MAX_PX, images.WEB_QUALITY), (1400, 68))
        self.assertEqual((images.THUMB_MAX_PX, images.THUMB_QUALITY), (480, 70))
