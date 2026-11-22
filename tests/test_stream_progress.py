import base64
import json
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from core import naify_api_work, naify_config


WEBP = b"RIFF\x04\x00\x00\x00WEBP"


class StreamProgressTests(unittest.TestCase):
    def test_sse_parser_handles_split_event_and_trailing_event(self):
        lines = [
            ": heartbeat", "event: intermediate",
            'data: {"step_ix": 0,', 'data: "steps": 2}',
            "", 'event: final',
            'data: {"image": "ZGF0YQ=="}'
        ]
        events = list(naify_api_work.iter_generation_events(lines))
        self.assertEqual(events[0], ("intermediate", {"step_ix": 0, "steps": 2}))
        self.assertEqual(events[1][0], "final")

    def test_stream_returns_webp_and_reports_actual_progress(self):
        lines = [
            "event: intermediate",
            'data: {"step_ix": 0, "steps": 4, "image": "preview-ignored"}', "",
            "event: intermediate",
            'data: {"step_ix": 2, "steps": 4, "image": "preview-ignored"}', "",
            "event: final",
            "data: " + json.dumps({"image": base64.b64encode(WEBP).decode("ascii")}), ""
        ]
        response = Mock(status_code=200)
        response.iter_lines.return_value = iter(lines)
        from unittest.mock import MagicMock
        stream = MagicMock()
        stream.return_value.__enter__.return_value = response

        progress = []
        with patch.object(naify_api_work.httpx, "stream", stream):
            image = naify_api_work.generate_image_stream(
                "image-id", naify_config.NaifySecrets(),
                naify_config.NaifyConfig(), "scene", "girl",
                on_progress=progress.append
            )

        self.assertEqual(image, WEBP)
        self.assertEqual(progress, [25, 75])
        args, kwargs = stream.call_args
        self.assertEqual(args, ("POST", naify_api_work.NAI_STREAM_URL))
        self.assertEqual(kwargs["json"]["parameters"]["stream"], "sse")

    def test_stream_fails_without_final_image(self):
        response = Mock(status_code=200)
        response.iter_lines.return_value = iter([
            "event: intermediate", 'data: {"step_ix": 1, "steps": 2}', ""
        ])
        from unittest.mock import MagicMock
        with patch.object(naify_api_work.httpx, "stream") as stream:
            stream.return_value.__enter__.return_value = response
            with self.assertRaises(HTTPException) as caught:
                naify_api_work.generate_image_stream(
                    "id", naify_config.NaifySecrets(),
                    naify_config.NaifyConfig(), "scene"
                )
        self.assertEqual(caught.exception.status_code, 502)

    def test_stream_rejects_rate_limit_without_retry(self):
        response = Mock(status_code=429, text='{"message":"locked"}')
        response.json.return_value = {"message": "locked"}
        with patch.object(naify_api_work.httpx, "stream") as stream:
            stream.return_value.__enter__.return_value = response
            with self.assertRaises(HTTPException) as caught:
                naify_api_work.generate_image_stream(
                    "id", naify_config.NaifySecrets(),
                    naify_config.NaifyConfig(), "scene"
                )
        self.assertEqual(caught.exception.status_code, 503)
        stream.assert_called_once()


if __name__ == "__main__":
    unittest.main()
