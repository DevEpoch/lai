"""Agent loop unit tests - pure parts only, no model needed."""
import tempfile
import unittest
from pathlib import Path

from laicore.agent import (_confine, auto_skill, detect_taskfile, mark_done,
                           parse_tasks, parse_tool_call, t_search)


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


class TestTaskRunner(unittest.TestCase):
    MD = ("# plan\n\n- [ ] add a login page\n- [x] set up repo\n"
          "1. write tests for auth\n* polish the README\nprose line\n")

    def test_parse_tasks_all_styles(self):
        tasks = parse_tasks(self.MD)
        texts = [t["text"] for t in tasks]
        self.assertEqual(len(tasks), 4)  # prose line is not a task
        self.assertIn("write tests for auth", texts)
        self.assertTrue(tasks[1]["done"])   # [x] line
        self.assertFalse(tasks[2]["done"])  # numbered line
        self.assertEqual(sum(t["box"] for t in tasks), 2)

    def test_mark_done_ticks_and_converts(self):
        out = mark_done(self.MD, 2)  # the [ ] checkbox line
        self.assertIn("- [x] add a login page", out)
        out = mark_done(out, 4)      # the numbered line becomes a box
        self.assertIn("- [x] write tests for auth", out)
        self.assertEqual(len([t for t in parse_tasks(out)
                              if not t["done"]]), 1)


    def test_detect_taskfile_routes_only_real_lists(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "plan.md").write_text("- [ ] one\n- [ ] two\n")
            f = detect_taskfile(d, "please do all the tasks in plan.md")
            self.assertIsNotNone(f)
            self.assertEqual(f.name, "plan.md")
            # no intent words -> normal agent, even if the file exists
            self.assertIsNone(detect_taskfile(d, "what is plan.md about?"))
            # intent but no such file -> normal agent
            self.assertIsNone(detect_taskfile(
                d, "do all the tasks in missing.md"))
            # escape attempt -> normal agent, never a path outside root
            self.assertIsNone(detect_taskfile(
                d, "do the tasks in ../../evil.md"))


if __name__ == "__main__":
    unittest.main()
