import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image

import main
from core import naify_cache
from core.naify_config import CacheConfig, NaifyConfig
from core.naify_image_optimizer import optimize_image
from core.naify_regeneration import make_regeneration_metadata


class RegenerationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = Image.new("RGB", (24, 24), "blue")
        data = io.BytesIO()
        image.save(data, format="WEBP")
        original_config = NaifyConfig()
        original_config.generation.steps = 36
        original_config.prompt.base_prompt = "original base"
        cls.source_bytes = optimize_image(
            data.getvalue(), metadata=make_regeneration_metadata(
                "lake", "red hair", "", "", original_config
            )
        )

    def request(self, origin="http://127.0.0.1:8000", action="regenerate-image"):
        return SimpleNamespace(headers={"origin": origin, "x-naify-action": action})

    def test_status_disables_regeneration_without_naify_metadata(self):
        with patch.object(main.naify_cache, "get_image_from_cache", return_value=self.source_bytes):
            result = main.get_regeneration_status("a" * 64)
        self.assertEqual(result, {"available": True})
        plain = io.BytesIO()
        Image.new("RGB", (16, 16), "red").save(plain, format="WEBP")
        with patch.object(main.naify_cache, "get_image_from_cache", return_value=plain.getvalue()):
            self.assertEqual(main.get_regeneration_status("a" * 64), {"available": False})

    def test_both_modes_force_queue_with_expected_generation_settings(self):
        current = NaifyConfig()
        current.generation.steps = 15
        current.prompt.base_prompt = "current base"
        current.cache.webp_quality = 93
        with patch.object(main, "naify_config", current), \
                patch.object(main.naify_cache, "get_image_from_cache", return_value=self.source_bytes), \
                patch.object(main.naify_image_fetcher, "fetch_image", return_value=b"regenerated") as fetch, \
                patch.object(main.app.state, "generation_worker", object(), create=True):
            for mode, steps, base in (
                ("original", 36, "original base"),
                ("current", 15, "current base"),
            ):
                response = main.regenerate_cached_image("a" * 64, mode, self.request())
                self.assertTrue(response["regenerated"])
                kwargs = fetch.call_args.kwargs
                self.assertTrue(kwargs["force_regeneration"])
                self.assertEqual(kwargs["prompt"], "lake")
                self.assertEqual(kwargs["char1"], "red hair")
                self.assertEqual(kwargs["config"].generation.steps, steps)
                self.assertEqual(kwargs["config"].prompt.base_prompt, base)
                self.assertEqual(kwargs["config"].cache.webp_quality, 93)

    def test_regeneration_requires_manager_origin_and_valid_image_id(self):
        for origin in ("https://evil.example", None):
            with self.assertRaises(HTTPException) as raised:
                main.regenerate_cached_image("a" * 64, "original", self.request(origin=origin))
            self.assertEqual(raised.exception.status_code, 403)
        with self.assertRaises(HTTPException) as raised:
            main.regenerate_cached_image("../escape", "current", self.request())
        self.assertEqual(raised.exception.status_code, 400)

    def test_old_cache_is_rejected_without_spending_generation(self):
        plain = io.BytesIO()
        Image.new("RGB", (16, 16), "red").save(plain, format="WEBP")
        with patch.object(main.naify_cache, "get_image_from_cache", return_value=plain.getvalue()), \
                patch.object(main.naify_image_fetcher, "fetch_image") as fetch:
            with self.assertRaises(HTTPException) as raised:
                main.regenerate_cached_image("a" * 64, "original", self.request())
        self.assertEqual(raised.exception.status_code, 409)
        fetch.assert_not_called()


class CachePolicyTests(unittest.TestCase):
    def test_legacy_image_count_limit_is_ignored(self):
        old = CacheConfig.model_validate({"max_images": 1, "max_cache_size": 4096})
        self.assertNotIn("max_images", old.model_dump())
        self.assertEqual(old.webp_quality, 90)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for letter in "abc":
                (root / (letter * 64 + ".webp")).write_bytes(b"1234")
            with patch.object(naify_cache, "CACHE_DIR", root):
                naify_cache.trim_cache(old)
                self.assertEqual(len(list(root.glob("*.webp"))), 3)

    def test_cache_trim_uses_bytes_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for letter in "abc":
                (root / (letter * 64 + ".webp")).write_bytes(b"1234")
            with patch.object(naify_cache, "CACHE_DIR", root):
                naify_cache.trim_cache(CacheConfig(max_cache_size=8))
                self.assertEqual(len(list(root.glob("*.webp"))), 2)


if __name__ == "__main__":
    unittest.main()
