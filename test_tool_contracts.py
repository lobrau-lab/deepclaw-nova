import unittest

from skills.registry import Skill, SkillRegistry


class ToolContractTests(unittest.TestCase):
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
