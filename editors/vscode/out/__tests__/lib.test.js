"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const vitest_1 = require("vitest");
const lib_1 = require("../lib");
const join = (...p) => p.join("/");
(0, vitest_1.describe)("findLaiHome", () => {
    (0, vitest_1.it)("returns the first candidate containing lai.py", () => {
        const fsx = { exists: (p) => p === "b/lai.py",
            read: () => "" };
        (0, vitest_1.expect)((0, lib_1.findLaiHome)(["a", "b", "c"], fsx, join)).toBe("b");
    });
    (0, vitest_1.it)("skips undefined candidates and returns null when none match", () => {
        const fsx = { exists: () => false, read: () => "" };
        (0, vitest_1.expect)((0, lib_1.findLaiHome)([undefined, "a"], fsx, join)).toBeNull();
    });
});
(0, vitest_1.describe)("portFromStateJson", () => {
    (0, vitest_1.it)("reads a configured port", () => {
        (0, vitest_1.expect)((0, lib_1.portFromStateJson)('{"ui": 9001}', "ui", 8090)).toBe(9001);
    });
    (0, vitest_1.it)("falls back on missing file, bad json, bad values", () => {
        (0, vitest_1.expect)((0, lib_1.portFromStateJson)(null, "ui", 8090)).toBe(8090);
        (0, vitest_1.expect)((0, lib_1.portFromStateJson)("not json", "ui", 8090)).toBe(8090);
        (0, vitest_1.expect)((0, lib_1.portFromStateJson)('{"ui": "x"}', "ui", 8090)).toBe(8090);
        (0, vitest_1.expect)((0, lib_1.portFromStateJson)('{"ui": 99999}', "ui", 8090)).toBe(8090);
    });
});
(0, vitest_1.describe)("apiKeyFromSecrets", () => {
    (0, vitest_1.it)("extracts the key and tolerates garbage", () => {
        (0, vitest_1.expect)((0, lib_1.apiKeyFromSecrets)('{"api_key": "k1"}')).toBe("k1");
        (0, vitest_1.expect)((0, lib_1.apiKeyFromSecrets)('{"cloud": {}}')).toBeNull();
        (0, vitest_1.expect)((0, lib_1.apiKeyFromSecrets)(null)).toBeNull();
        (0, vitest_1.expect)((0, lib_1.apiKeyFromSecrets)("oops")).toBeNull();
    });
});
(0, vitest_1.describe)("lastCodeBlock", () => {
    (0, vitest_1.it)("returns the last fenced block", () => {
        const md = "a\n```py\nfirst\n```\nb\n```js\nsecond()\n```\n";
        (0, vitest_1.expect)((0, lib_1.lastCodeBlock)(md)).toBe("second()\n");
    });
    (0, vitest_1.it)("returns null without fences", () => {
        (0, vitest_1.expect)((0, lib_1.lastCodeBlock)("no code here")).toBeNull();
    });
});
(0, vitest_1.describe)("sseToken", () => {
    (0, vitest_1.it)("parses streaming deltas", () => {
        const line = 'data: {"choices":[{"delta":{"content":"hi"}}]}';
        (0, vitest_1.expect)((0, lib_1.sseToken)(line)).toBe("hi");
    });
    (0, vitest_1.it)("ignores DONE, blanks, and junk", () => {
        (0, vitest_1.expect)((0, lib_1.sseToken)("data: [DONE]")).toBeNull();
        (0, vitest_1.expect)((0, lib_1.sseToken)("")).toBeNull();
        (0, vitest_1.expect)((0, lib_1.sseToken)("event: ping")).toBeNull();
        (0, vitest_1.expect)((0, lib_1.sseToken)("data: not-json")).toBeNull();
    });
});
