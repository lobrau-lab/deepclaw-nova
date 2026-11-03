import unittest

from skills.registry import Skill, SkillRegistry
from voice.assistant import NovaVoiceAssistant
from core.harness import build_system_prompt


class ToolContractTests(unittest.TestCase):
    def test_system_prompt_sets_truthful_persistent_copilot_contract(self):
        prompt, _ = build_system_prompt("base", "qwen3.5")
        self.assertIn("user's DeepClaw AI co-pilot", prompt)
        self.assertIn("Never lie, guess, or claim", prompt)
        self.assertIn("Persist through recoverable errors", prompt)
        self.assertIn("fail closed", prompt)

    def test_casual_requests_skip_tool_mode(self):
        self.assertTrue(NovaVoiceAssistant._is_casual_request("hello"))
        self.assertTrue(NovaVoiceAssistant._is_casual_request("Thanks!"))
        self.assertFalse(NovaVoiceAssistant._is_casual_request("open Safari"))
        self.assertEqual(NovaVoiceAssistant._casual_response("hello"), "Hello! I'm ready to help.")
        self.assertEqual(NovaVoiceAssistant._casual_response("thanks"), "You're welcome!")

    def test_rejects_unknown_arguments(self):
        registry = SkillRegistry()
        registry.register(Skill(
            name="bounded",
            description="test",
            parameters={
                "type": "object",
                "properties": {"mode": {"type": "string", "enum": ["read"]}},
                "required": ["mode"],
                "additionalProperties": False,
            },
            handler=lambda mode: mode,
        ))

        result = registry.execute("bounded", {"mode": "read", "extra": True})
        self.assertIn("unknown argument", result)

    def test_rejects_values_outside_enum(self):
        registry = SkillRegistry()
        registry.register(Skill(
            name="bounded",
            description="test",
            parameters={
                "type": "object",
                "properties": {"mode": {"type": "string", "enum": ["read"]}},
                "required": ["mode"],
            },
            handler=lambda mode: mode,
        ))

        result = registry.execute("bounded", {"mode": "write"})
        self.assertIn("must be one of", result)


if __name__ == "__main__":
    unittest.main()
