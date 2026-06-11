"""lai test suite - stdlib unittest only, fully offline, read-only.

Run:  python -m unittest discover -s tests -v     (or: lai selftest)

These tests never touch state/, models/, or the network. They cover the
planning kernel, parsers, the catalog's internal consistency, the i18n
dictionaries, and the built UI artifacts.
"""
import json
import re
import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from laicore import core, stack, work  # noqa: E402

CAT = json.loads((ROOT / "config" / "catalog.json").read_text(
    encoding="utf-8"))

HW_LAPTOP = {"platform": "windows", "vendor": "nvidia", "vram_gb": 6.0,
             "ram_gb": 31.7, "gpus": [{"index": 0, "name": "t",
                                       "mem_mib": 6144}], "cores": 12}
HW_3090 = {"platform": "linux", "vendor": "nvidia", "vram_gb": 24.0,
           "ram_gb": 64.0, "gpus": [{"index": 0, "name": "3090",
                                     "mem_mib": 24576}], "cores": 16}
HW_MAC64 = {"platform": "mac", "vendor": "apple", "vram_gb": 64.0,
            "ram_gb": 64.0, "gpus": [{"index": 0, "name": "m",
                                      "mem_mib": 65536}], "cores": 12}
HW_CPU = {"platform": "linux", "vendor": "none", "vram_gb": 0,
          "ram_gb": 32.0, "gpus": [], "cores": 8}


class TestPlanningKernel(unittest.TestCase):
    def test_tier_matching(self):
        cases = [(HW_LAPTOP, "gpu-8gb-bigram"), (HW_3090, "gpu-24gb"),
                 (HW_MAC64, "apple-64gb"), (HW_CPU, "cpu-32gb")]
        for hw, expect in cases:
            tier = core.match_tier(CAT, hw)
            self.assertIsNotNone(tier, hw)
            self.assertEqual(tier["id"], expect)

    def test_low_ram_laptop_avoids_hybrid_tier(self):
        hw = dict(HW_LAPTOP, ram_gb=16.0)
        self.assertEqual(core.match_tier(CAT, hw)["id"], "gpu-8gb")

    def test_explicit_null_default_stays_disabled(self):
        tier = core.match_tier(CAT, HW_LAPTOP)
        choices = core.build_choices(CAT, tier, HW_LAPTOP)
        self.assertIsNone(choices["roles"]["thinker"],
                          "tier sets thinker null; fallback must not "
                          "re-enable it")
        self.assertIsNotNone(choices["roles"]["coder"])

    def test_fit_modes(self):
        self.assertEqual(core.fit_mode(CAT, "qwen3-coder-30b-a3b",
                                       HW_LAPTOP), "hybrid")
        self.assertEqual(core.fit_mode(CAT, "qwen3-coder-30b-a3b",
                                       HW_3090), "gpu")
        self.assertEqual(core.fit_mode(CAT, "qwen3-coder-30b-a3b",
                                       HW_CPU), "cpu")
        self.assertIsNone(core.fit_mode(CAT, "devstral-small", HW_LAPTOP))
        self.assertEqual(core.fit_mode(CAT, "gemma-4-26b-a4b", HW_MAC64),
                         "gpu")

    def test_usecase_overlays(self):
        tier = core.match_tier(CAT, HW_3090)
        ch = core.build_choices(CAT, tier, HW_3090)
        core.apply_usecase(CAT, ch, "scripts")
        self.assertIsNone(ch["roles"]["vision"])
        self.assertIsNone(ch["roles"]["thinker"])
        ch2 = core.build_choices(CAT, tier, HW_3090)
        coder_ctx = ch2["roles"]["coder"]["ctx"]
        core.apply_usecase(CAT, ch2, "web")
        self.assertLessEqual(ch2["roles"]["coder"].get("ctx", 0), coder_ctx,
                             "overlay must never raise a big-role ctx")
        self.assertEqual(ch2["roles"]["autocomplete"]["ctx"], 16384,
                         "side roles may raise ctx")

    def test_set_choice(self):
        tier = core.match_tier(CAT, HW_3090)
        ch = core.build_choices(CAT, tier, HW_3090)
        with self.assertRaises(ValueError):
            core.set_choice(CAT, ch, "nope", "qwen3-4b")
        with self.assertRaises(ValueError):
            core.set_choice(CAT, ch, "coder", "not-a-model")
        with self.assertRaises(ValueError):  # misfit without force
            core.set_choice(CAT, dict(ch, hardware=HW_LAPTOP), "coder",
                            "devstral-small")
        core.set_choice(CAT, ch, "coder", "none")
        self.assertIsNone(ch["roles"]["coder"])
        warnings = core.set_choice(CAT, ch, "coder", "gemma-4-26b-a4b")
        self.assertEqual(ch["roles"]["coder"]["model"], "gemma-4-26b-a4b")
        self.assertEqual(warnings, [])

    def test_parse_model(self):
        self.assertEqual(core.parse_model("coder"), (None, "coder"))
        self.assertEqual(core.parse_model("or:qwen/x"),
                         ("openrouter", "qwen/x"))
        self.assertEqual(core.parse_model("an:claude-x"),
                         ("anthropic", "claude-x"))

    def test_sanitize_name(self):
        self.assertEqual(core.sanitize_name("My App 2!"), "my_app_2")
        self.assertEqual(core.sanitize_name("123"), "project")


class TestParsers(unittest.TestCase):
    def test_split_conflicts(self):
        text = ("a\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> br\nb\n")
        parts = work.split_conflicts(text)
        kinds = [p[0] for p in parts]
        self.assertIn("conflict", kinds)
        c = parts[kinds.index("conflict")]
        self.assertEqual(c[1], "ours\n")
        self.assertEqual(c[2], "theirs\n")

    def test_split_conflicts_diff3(self):
        text = ("<<<<<<< HEAD\nours\n||||||| base\nold\n=======\n"
                "theirs\n>>>>>>> br\n")
        parts = work.split_conflicts(text)
        c = [p for p in parts if p[0] == "conflict"][0]
        self.assertEqual(c[1], "ours\n")
        self.assertEqual(c[2], "theirs\n")

    def test_extract_fenced(self):
        self.assertEqual(work._extract_fenced("x\n```py\ncode\n```\ny"),
                         "code\n")

    def test_chunking(self):
        text = "\n\n".join(f"paragraph {i} " + "x" * 300 for i in range(12))
        chunks = work._chunk(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 4000 for c in chunks))

    def test_html_to_text(self):
        out = work._html_to_text(
            "<html><script>bad()</script><p>Hello &amp; bye</p></html>")
        self.assertIn("Hello & bye", out)
        self.assertNotIn("bad()", out)

    def test_render_bar(self):
        self.assertEqual(len(core.render_bar(0, 10)), 10)
        self.assertEqual(len(core.render_bar(100, 10)), 10)
        self.assertEqual(len(core.render_bar(250, 10)), 10)

    def test_version_ordering(self):
        self.assertGreater(stack.ver_key("0.10.0"), stack.ver_key("0.9.3"))
        self.assertGreater(stack.ver_key("1.0.0"), stack.ver_key("0.10.0"))

    def test_changelog_delta(self):
        delta = stack._changelog_delta("0.9.3")
        self.assertIn("[0.10.0]", delta)
        self.assertNotIn("[0.9.3]", delta)
        self.assertNotIn("[0.9.0]", delta)


class TestCatalogIntegrity(unittest.TestCase):
    def test_models_have_required_fields(self):
        for mid, m in CAT["models"].items():
            self.assertTrue(m.get("repo"), mid)
            self.assertTrue(m.get("include"), mid)
            self.assertIsInstance(m.get("disk_gb"), (int, float), mid)
            self.assertTrue(set(m.get("roles", [])) <= set(core.ROLES), mid)

    def test_tier_defaults_reference_known_models(self):
        for t in CAT["tiers"]:
            for role, d in t.get("defaults", {}).items():
                self.assertIn(role, core.ROLES, t["id"])
                mid = (d or {}).get("model")
                if mid is not None:
                    self.assertIn(mid, CAT["models"],
                                  f"{t['id']}.{role} -> {mid}")

    def test_every_tier_has_a_runnable_coder(self):
        for t in CAT["tiers"]:
            hw = {"platform": t.get("platform", ["linux"])[0],
                  "vendor": t.get("vendor", ["none"])[0],
                  "vram_gb": t.get("min_vram_gb", 0) or
                  (t.get("min_ram_gb", 8) if "apple" in
                   t.get("vendor", [""])[0] else 0),
                  "ram_gb": max(t.get("min_ram_gb", 8), 8),
                  "gpus": [], "cores": 8}
            if hw["vendor"] == "apple":
                hw["ram_gb"] = max(t.get("min_ram_gb", 8), 8)
                hw["vram_gb"] = hw["ram_gb"]
            self.assertTrue(core.candidates(CAT, "coder", hw),
                            f"no coder fits tier {t['id']} minimums")

    def test_stacks_reference_known_usecases(self):
        for sid, s in CAT["stacks"].items():
            if sid.startswith("_"):
                continue
            self.assertIn(s["usecase"], CAT["usecases"], sid)
            self.assertTrue(set(s.get("required_roles", []))
                            <= set(core.ROLES), sid)

    def test_engines_cover_all_platform_vendor_combos(self):
        for plat in ("windows", "linux"):
            for vend in ("nvidia", "amd", "none"):
                key = core.engine_key({"platform": plat, "vendor": vend})
                self.assertIn(key, CAT["engines"], key)
        self.assertIn("mac-metal", CAT["engines"])
        for osname in ("windows", "linux", "mac"):
            self.assertIn(osname, CAT["engines"]["llama_swap"])


class TestQualitySuite(unittest.TestCase):
    def test_python_task_tests_compile(self):
        for t in stack.QUALITY_TASKS:
            self.assertTrue(t.get("prompt"), t["id"])
            if t["type"] == "python":
                compile(t["test"], t["id"], "exec")
            elif t["type"] == "tool":
                self.assertTrue(t.get("tools") and t.get("expect_tool"),
                                t["id"])
            else:
                re.compile(t["pattern"])


class TestPorts(unittest.TestCase):
    def test_port_free_detects_listener(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            self.assertFalse(core.port_free(port))
            free = core.next_free_port(port)
            self.assertNotEqual(free, port)
            self.assertTrue(core.port_free(free))
        finally:
            s.close()


class TestUIArtifacts(unittest.TestCase):
    I18N = (ROOT / "ui" / "src" / "i18n.ts").read_text(encoding="utf-8")
    APP = (ROOT / "ui" / "src" / "App.vue").read_text(encoding="utf-8")

    def lang_keys(self, lang):
        m = re.search(rf"\n  {lang}: \{{(.*?)\n  \}},", self.I18N, re.S)
        self.assertIsNotNone(m, f"no {lang} section")
        return set(re.findall(r'"([a-z0-9.]+)":', m.group(1)))

    def test_translations_have_identical_keys(self):
        en, fa, ar = (self.lang_keys(x) for x in ("en", "fa", "ar"))
        self.assertEqual(en, fa, "fa keys differ from en")
        self.assertEqual(en, ar, "ar keys differ from en")
        self.assertGreater(len(en), 40)

    def test_app_uses_only_known_keys(self):
        en = self.lang_keys("en")
        used = set(re.findall(r"""t\(["']([a-z0-9.]+)["']\)""", self.APP))
        used |= set(re.findall(r'label: "([a-z0-9.]+)"', self.APP))
        missing = {k for k in used if k not in en}
        self.assertFalse(missing, f"App.vue uses unknown i18n keys: "
                                  f"{missing}")

    def test_dynamic_home_keys_exist(self):
        en = self.lang_keys("en")
        for state in ("setup", "down", "start", "ready"):
            for part in ("big", "small"):
                self.assertIn(f"home.{state}.{part}", en)

    def test_dist_is_built_and_consistent(self):
        dist = ROOT / "ui" / "dist"
        index = (dist / "index.html").read_text(encoding="utf-8")
        for ref in re.findall(r'assets/[\w.-]+\.(?:js|css)', index):
            self.assertTrue((dist / ref).exists(), f"missing {ref}")


class TestRepoHygiene(unittest.TestCase):
    def test_changelog_has_current_version(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"[{core.VERSION}]", text,
                      "VERSION bumped without a CHANGELOG entry")

    def test_skills_are_well_formed(self):
        for d in (ROOT / "skills").iterdir():
            meta = json.loads((d / "skill.json").read_text(encoding="utf-8"))
            self.assertTrue(meta.get("description"), d.name)
            payload = list((d / "project").rglob("*")) \
                if (d / "project").exists() else []
            self.assertTrue(payload or meta.get("mode"), d.name)

    def test_state_is_gitignored(self):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for must in ("state/", "models/", "tools/"):
            self.assertIn(must, gi)


if __name__ == "__main__":
    unittest.main()
