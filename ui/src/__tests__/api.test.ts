import { afterEach, describe, expect, it, vi } from "vitest";
import { get, post } from "../api";

function mockFetch(status: number, body: unknown): void {
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body,
  })));
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("get returns parsed json", async () => {
    mockFetch(200, { hello: 1 });
    expect(await get<{ hello: number }>("/api/x")).toEqual({ hello: 1 });
  });

  it("get throws the server error payload", async () => {
    mockFetch(409, { error: "already running" });
    await expect(get("/api/x")).rejects.toEqual({ error: "already running" });
  });

  it("post sends json and returns the response", async () => {
    mockFetch(200, { ok: true });
    expect(await post("/api/y", { a: 1 })).toEqual({ ok: true });
    const call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toBe("/api/y");
    expect(call[1].method).toBe("POST");
    expect(JSON.parse(call[1].body)).toEqual({ a: 1 });
  });

  it("post throws on http error", async () => {
    mockFetch(400, { error: "bad" });
    await expect(post("/api/y")).rejects.toEqual({ error: "bad" });
  });
});
