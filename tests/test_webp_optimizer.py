import io
import unittest

from PIL import Image

from core.naify_image_optimizer import WEBP_METHOD, WEBP_QUALITY, optimize_image


class WebPOptimizationTests(unittest.TestCase):
    def test_quality_80_removes_metadata_and_preserves_dimensions(self):
        image = Image.new("RGB", (48, 32), (30, 120, 190))
        source = io.BytesIO()
        image.save(source, format="WEBP", quality=100, exif=b"TEST EXIF", xmp=b"TEST XMP")
        result = optimize_image(source.getvalue())
        with Image.open(io.BytesIO(result)) as optimized:
            self.assertEqual(optimized.size, image.size)
            self.assertEqual(optimized.format, "WEBP")
            self.assertNotIn("exif", optimized.info)
            self.assertNotIn("xmp", optimized.info)
        self.assertEqual(WEBP_QUALITY, 80)
        self.assertEqual(WEBP_METHOD, 4)

    def test_preserves_alpha(self):
        source = io.BytesIO()
        Image.new("RGBA", (32, 32), (230, 45, 70, 0)).save(source, format="WEBP")
        with Image.open(io.BytesIO(optimize_image(source.getvalue()))) as result:
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.getpixel((0, 0))[3], 0)


if __name__ == "__main__":
    unittest.main()
