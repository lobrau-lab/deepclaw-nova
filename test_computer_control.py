import unittest
from unittest.mock import patch

from control.macos_bridge import ComputerController


class ComputerControlTests(unittest.TestCase):
    @patch("control.macos_bridge.run_applescript", return_value=(True, ""))
    def test_escapes_applescript_text(self, run_script):
        ComputerController().show_notification('A"title', 'line 1\nline 2 \\ ok')
        script = run_script.call_args.args[0]
        self.assertIn('A\\"title', script)
        self.assertIn('line 1\\nline 2 \\\\ ok', script)

    def test_rejects_unallowlisted_media_actions(self):
        result = ComputerController().media_control('play; do shell script "bad"')
        self.assertIn("Unsupported media action", result)

    @patch("control.macos_bridge.run_applescript", return_value=(True, ""))
    def test_maps_media_actions_to_fixed_applescript(self, run_script):
        ComputerController().media_control("next")
        script = run_script.call_args.args[0]
        self.assertIn("next track", script)
        self.assertNotIn("next\\\"", script)


if __name__ == "__main__":
    unittest.main()
