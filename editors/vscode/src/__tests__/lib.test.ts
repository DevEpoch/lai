import { describe, expect, it } from "vitest";
import { apiKeyFromSecrets, findLaiHome, lastCodeBlock, pickRole,
         portFromStateJson, sseToken } from "../lib";

const join = (...p: string[]) => p.join("/");

describe("findLaiHome", () => {
  it("returns the first candidate containing lai.py", () => {
    const fsx = { exists: (p: string) => p === "b/lai.py",
                  read: () => "" };
    expect(findLaiHome(["a", "b", "c"], fsx, join)).toBe("b");
  });
  it("skips undefined candidates and returns null when none match", () => {
    const fsx = { exists: () => false, read: () => "" };
    expect(findLaiHome([undefined, "a"], fsx, join)).toBeNull();
  });
});

describe("pickRole", () => {
  it("routes coding verbs to coder", () => {
    expect(pickRole("fix this bug in my parser")).toBe("coder");
    expect(pickRole("write a regex for emails")).toBe("coder");
  });
  it("routes reasoning and translation to thinker", () => {
    expect(pickRole("explain why this design is better")).toBe("thinker");
    expect(pickRole("translate this paragraph to French")).toBe("thinker");
  });
  it("routes Persian/Arabic reasoning words to thinker", () => {
    expect(pickRole("این متن را ترجمه کن")).toBe("thinker");
    expect(pickRole("اشرح هذا الكود")).toBe("thinker");
  });
  it("coding verbs win over reasoning verbs; code blocks mean coder", () => {
    expect(pickRole("explain and fix this error")).toBe("coder");
    expect(pickRole("what does this do?\n```js\nx()\n```")).toBe("coder");
  });
  it("defaults to coder", () => {
    expect(pickRole("hello")).toBe("coder");
  });
});

describe("portFromStateJson", () => {
  it("reads a configured port", () => {
    expect(portFromStateJson('{"ui": 9001}', "ui", 8090)).toBe(9001);
  });
  it("falls back on missing file, bad json, bad values", () => {
    expect(portFromStateJson(null, "ui", 8090)).toBe(8090);
    expect(portFromStateJson("not json", "ui", 8090)).toBe(8090);
    expect(portFromStateJson('{"ui": "x"}', "ui", 8090)).toBe(8090);
    expect(portFromStateJson('{"ui": 99999}', "ui", 8090)).toBe(8090);
  });
});

describe("apiKeyFromSecrets", () => {
  it("extracts the key and tolerates garbage", () => {
    expect(apiKeyFromSecrets('{"api_key": "k1"}')).toBe("k1");
    expect(apiKeyFromSecrets('{"cloud": {}}')).toBeNull();
    expect(apiKeyFromSecrets(null)).toBeNull();
    expect(apiKeyFromSecrets("oops")).toBeNull();
  });
});

describe("lastCodeBlock", () => {
  it("returns the last fenced block", () => {
    const md = "a\n```py\nfirst\n```\nb\n```js\nsecond()\n```\n";
    expect(lastCodeBlock(md)).toBe("second()\n");
  });
  it("returns null without fences", () => {
    expect(lastCodeBlock("no code here")).toBeNull();
  });
});

describe("sseToken", () => {
  it("parses streaming deltas", () => {
    const line = 'data: {"choices":[{"delta":{"content":"hi"}}]}';
    expect(sseToken(line)).toBe("hi");
  });
  it("ignores DONE, blanks, and junk", () => {
    expect(sseToken("data: [DONE]")).toBeNull();
    expect(sseToken("")).toBeNull();
    expect(sseToken("event: ping")).toBeNull();
    expect(sseToken("data: not-json")).toBeNull();
  });
});
