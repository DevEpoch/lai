"""Agent loop unit tests - pure parts only, no model needed."""
import tempfile
import unittest
from pathlib import Path

from laicore.agent import _confine, auto_skill, parse_tool_call, t_search


class TestAgent(unittest.TestCase):
    def test_parse_tool_call(self):
        txt = 'x\n```tool\n{"tool": "read_file", "args": {"path": "a"}}\n```'
        self.assertEqual(parse_tool_call(txt),
                         ("read_file", {"path": "a"}))
        self.assertIsNone(parse_tool_call("no tools here"))
        self.assertIsNone(parse_tool_call(
            '```tool\n{"tool": "rm_rf", "args": {}}\n```'))

    def test_confine_blocks_escape(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(str(_confine(d, "sub/x.py")).startswith(
                str(Path(d).resolve())))
            with self.assertRaises(ValueError):
                _confine(d, "../outside.txt")

    def test_search_and_skill_match(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text("def hello():\n    pass\n")
            self.assertIn("m.py:1", t_search(d, r"def hello"))
        text, name = auto_skill("please review my code for problems")
        self.assertIsNotNone(name)  # some relevant skill was matched
        self.assertIn("Active skill", text)


if __name__ == "__main__":
    unittest.main()
