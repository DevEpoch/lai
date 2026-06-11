import { describe, expect, it } from "vitest";
import { apiKeyFromSecrets, findLaiHome, lastCodeBlock, portFromStateJson,
         sseToken } from "../lib";

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
