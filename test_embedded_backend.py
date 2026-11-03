import sys
import types
import unittest
from unittest.mock import patch

from core.residency import ModelResidencyManager


class EmbeddedBackendTests(unittest.TestCase):
    def test_generates_in_process_without_http(self):
        class Result:
            text = "embedded answer"
            generation_tokens = 2
            prompt_tokens = 4
            cached_tokens = 0
            prompt_tps = 100.0
            generation_tps = 20.0
            peak_memory = 1.0

        fake_mlx_vlm = types.ModuleType("mlx_vlm")
        fake_mlx_vlm.stream_generate = lambda *args, **kwargs: iter([Result()])
        fake_prompt_utils = types.ModuleType("mlx_vlm.prompt_utils")
        fake_prompt_utils.apply_chat_template = lambda *args, **kwargs: "formatted prompt"

        manager = ModelResidencyManager.__new__(ModelResidencyManager)
        manager.backend = "embedded"
        manager.model_name = "native-qwen"
        manager._ensure_embedded_loaded = lambda: True
        ModelResidencyManager._model = types.SimpleNamespace(config={})
        ModelResidencyManager._processor = object()

        with patch.dict(sys.modules, {
            "mlx_vlm": fake_mlx_vlm,
            "mlx_vlm.prompt_utils": fake_prompt_utils,
        }), patch.object(manager, "_chat_omlx") as http_chat:
            result = manager._chat_embedded(
                [{"role": "user", "content": "hello"}],
                None,
                32,
                0.0,
            )

        self.assertEqual(result["message"]["content"], "embedded answer")
        http_chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
