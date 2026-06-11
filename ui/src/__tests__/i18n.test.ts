import { describe, expect, it } from "vitest";
import { RTL_LANGS, STRINGS, lang, t } from "../i18n";

describe("i18n", () => {
  it("all languages have identical key sets", () => {
    const en = Object.keys(STRINGS.en).sort();
    expect(Object.keys(STRINGS.fa).sort()).toEqual(en);
    expect(Object.keys(STRINGS.ar).sort()).toEqual(en);
    expect(en.length).toBeGreaterThan(40);
  });

  it("no translation is empty", () => {
    for (const l of ["en", "fa", "ar"] as const) {
      for (const [k, v] of Object.entries(STRINGS[l])) {
        expect(v.trim(), `${l}.${k}`).not.toBe("");
      }
    }
  });

  it("t() falls back to english, then to the key", () => {
    lang.value = "fa";
    expect(t("nav.home")).toBe(STRINGS.fa["nav.home"]);
    expect(t("definitely.not.a.key")).toBe("definitely.not.a.key");
    lang.value = "en";
  });

  it("switching to fa/ar flips the document to RTL and back", async () => {
    for (const l of RTL_LANGS) {
      lang.value = l;
      await Promise.resolve(); // let watchEffect run
      expect(document.documentElement.dir).toBe("rtl");
      expect(document.documentElement.lang).toBe(l);
    }
    lang.value = "en";
    await Promise.resolve();
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("persists the chosen language", async () => {
    lang.value = "ar";
    await Promise.resolve();
    expect(localStorage.getItem("lai-lang")).toBe("ar");
    lang.value = "en";
  });
});
