import json
import unittest
from unittest.mock import patch

import config
from core.residency import ModelResidencyManager


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path":"/tmp/example.txt"}',
                        },
                    }],
                },
            }],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        }).encode()


class OmlxBackendTests(unittest.TestCase):
    def test_default_model_is_the_installed_omlx_gemma(self):
        self.assertEqual(
            config.DEFAULT_MODEL,
            "gemma-4-E4B-it-ultra-uncensored-heretic-MLX-4bit-mixed_4_6",
        )
        self.assertEqual(config.MODEL_BACKEND, "omlx")

    @patch("core.residency.urllib.request.urlopen", return_value=FakeResponse())
    def test_translates_openai_tool_calls(self, urlopen):
        manager = ModelResidencyManager.__new__(ModelResidencyManager)
        manager.backend = "omlx"
        manager.model_name = config.DEFAULT_MODEL

        result = manager._chat_omlx(
            [{"role": "user", "content": "read the file"}],
            [{"type": "function", "function": {"name": "read_file"}}],
            100,
            0.2,
        )

        call = result["message"]["tool_calls"][0]
        self.assertEqual(call["function"]["name"], "read_file")
        self.assertEqual(call["function"]["arguments"]["path"], "/tmp/example.txt")
        self.assertEqual(result["prompt_tokens"], 12)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, f"{config.OMLX_URL}/v1/chat/completions")
        self.assertFalse(json.loads(request.data)["chat_template_kwargs"]["enable_thinking"])
        if config.OMLX_API_KEY:
            self.assertNotIn(config.OMLX_API_KEY, request.data.decode())


if __name__ == "__main__":
    unittest.main()
