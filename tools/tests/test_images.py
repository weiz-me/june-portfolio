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

    def test_dimensions_handles_float_values_from_pdfs(self):
        # sips reports PDF page dimensions as floats (e.g., 959.760).
        # Create a minimal PDF and verify dimensions() rounds to int.
        pdf_path = os.path.join(self.tmp, "test.pdf")
        self._write_minimal_pdf(pdf_path)
        w, h = images.dimensions(pdf_path)
        # Both should be integers (not floats), and in reasonable range for a page.
        self.assertIsInstance(w, int)
        self.assertIsInstance(h, int)
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_dimensions_raises_sipserror_on_non_numeric_dimension(self):
        # Simulate sips returning a non-numeric, non-<nil> dimension value.
        # Use monkeypatch to avoid depending on sips quirks.
        original_sips = images._sips

        def mock_sips_bad_output(args):
            return "test.txt\n  pixelWidth: invalid\n  pixelHeight: 100\n"

        try:
            images._sips = mock_sips_bad_output
            with self.assertRaises(images.SipsError) as cm:
                images.dimensions(os.path.join(self.tmp, "test.txt"))
            self.assertIn("unparseable dimension", str(cm.exception))
        finally:
            images._sips = original_sips

    @staticmethod
    def _write_minimal_pdf(path):
        """Write a minimal valid PDF file (~8.5 x 11 inches at 72 DPI ~= 612 x 792 points)."""
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< >>
stream
BT
/F1 12 Tf
50 750 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000203 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
290
%%EOF
"""
        with open(path, "wb") as f:
            f.write(pdf_content)
