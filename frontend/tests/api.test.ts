import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "@/lib/api";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("apiFetch cold-start retries", () => {
  it("retries a read through a waking server and returns the data", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json(503, { error: { message: "waking", code: "error" } }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const result = apiFetch<{ ok: boolean }>("http://api/x");
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(result).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("gives up on a read after three attempts", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(json(502, null));
    vi.stubGlobal("fetch", fetchMock);
    const result = apiFetch("http://api/x");
    const assertion = expect(result).rejects.toMatchObject({ status: 502 });
    await vi.advanceTimersByTimeAsync(10_000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("never retries a write", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(503, null));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("http://api/x", { method: "POST" })).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a real client error", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(404, { error: { message: "Not found", code: "not_found" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("http://api/x")).rejects.toMatchObject({ status: 404, message: "Not found" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
