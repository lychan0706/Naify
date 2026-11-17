import asyncio
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from core import naify_api_work, naify_config, naify_image_fetcher, naify_utility
import main


class ReleaseFixTests(unittest.TestCase):
    def test_old_config_with_seed_still_loads(self):
        config = naify_config.NaifyConfig.model_validate({"generation": {"seed": 12345}})
        self.assertNotIn("seed", config.generation.model_dump())

    def test_log_waiter_wakes_up_on_new_log(self):
        seen = naify_utility.last_log_id
        result = []
        waiter = threading.Thread(target=lambda: result.extend(naify_utility.wait_for_logs(seen)))
        waiter.start()
        time.sleep(0.05)
        naify_utility.print_log(content="test log notification")
        waiter.join(timeout=0.5)
        self.assertFalse(waiter.is_alive(), "log waiter should wake before its one-second timeout")
        self.assertTrue(result)

    def test_non_json_api_error_is_translated_to_502(self):
        response = Mock(status_code=503, text="Service Unavailable")
        response.json.side_effect = ValueError("not JSON")
        with patch.object(naify_api_work.httpx, "post", return_value=response):
            with self.assertRaises(HTTPException) as raised:
                naify_api_work.generate_image("id", naify_config.NaifySecrets(), naify_config.NaifyConfig(), "prompt")
        self.assertEqual(raised.exception.status_code, 502)

    def test_generation_request_omits_seed(self):
        response = Mock(status_code=200, content=b"zip-data")
        with patch.object(naify_api_work.httpx, "post", return_value=response) as post, \
                patch.object(naify_api_work, "extract_image_from_zip", return_value=b"webp"):
            naify_api_work.generate_image("id", naify_config.NaifySecrets(), naify_config.NaifyConfig(), "prompt")
        self.assertNotIn("seed", post.call_args.kwargs["json"]["parameters"])

    def test_atomic_save_keeps_previous_file_on_replace_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "config.json"
            destination.write_text("original", encoding="utf-8")
            with patch.object(naify_config.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    naify_config.save_json_atomically(destination, "replacement")
            self.assertEqual(destination.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(Path(directory).iterdir()), [destination])
            naify_config.save_json_atomically(destination, "replacement")
            self.assertEqual(destination.read_text(encoding="utf-8"), "replacement")

    def test_dead_worker_returns_503(self):
        stopped_worker = threading.Thread(target=lambda: None)
        with patch.object(naify_image_fetcher, "get_image_from_cache", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                naify_image_fetcher.fetch_image(
                    "id", naify_config.NaifySecrets(), naify_config.NaifyConfig(),
                    "prompt", stopped_worker
                )
        self.assertEqual(raised.exception.status_code, 503)


class ShutdownStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_log_stream_closes_on_shutdown(self):
        request = SimpleNamespace(
            app=main.app,
            is_disconnected=AsyncMock(return_value=False)
        )
        release_waiter = threading.Event()

        def wait_for_logs_until_released(last_seen_id):
            release_waiter.wait(timeout=2.0)
            return [(1, "test log")]

        main.app.state.shutting_down = False
        try:
            with patch.object(main, "wait_for_logs", side_effect=wait_for_logs_until_released):
                response = await main.stream_logs(request)
                next_event = asyncio.create_task(response.body_iterator.__anext__())
                await asyncio.sleep(0.05)
                main.app.state.shutting_down = True
                release_waiter.set()

                with self.assertRaises(StopAsyncIteration):
                    await asyncio.wait_for(next_event, timeout=2.0)
        finally:
            release_waiter.set()
            main.app.state.shutting_down = False


if __name__ == "__main__":
    unittest.main()
