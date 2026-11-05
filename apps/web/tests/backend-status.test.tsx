import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { BackendStatus } from "../src/components/diagnostics/backend-status";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function reply(readiness: string, qdrant: string) {
  return new Response(JSON.stringify({ backend: "online", readiness, qdrant, request_id: "id" }));
}
test("shows loading", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => {})),
  );
  render(<BackendStatus />);
  expect(screen.getByText("Állapot ellenőrzése…")).toBeTruthy();
});
test.each([
  ["ready", "up", "A rendszer készen áll."],
  ["not_ready", "down", "A backend elérhető. A Qdrant-kapcsolat még nem áll készen."],
  ["unknown", "unknown", "A backend elérhető. A Qdrant állapota ismeretlen."],
])("renders %s", async (state, qdrant, message) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(state, qdrant)));
  render(<BackendStatus />);
  expect(await screen.findByText(message)).toBeTruthy();
});
test.each([503, 504])("handles failure %s", async (status) => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          backend: "offline",
          readiness: "unknown",
          qdrant: "unknown",
          request_id: "id",
          error: { code: "error" },
        }),
        { status },
      ),
    ),
  );
  render(<BackendStatus />);
  expect(
    await screen.findByText(
      status === 504
        ? "A backend válaszára várakozás lejárt."
        : "A backend nem érhető el. Próbáld újra.",
    ),
  ).toBeTruthy();
});
test("handles malformed response and retries once", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response("bad"))
    .mockResolvedValueOnce(reply("ready", "up"));
  vi.stubGlobal("fetch", fetchMock);
  render(<BackendStatus />);
  await screen.findByText("A backend válasza nem értelmezhető. Próbáld újra.");
  const button = screen.getByRole("button", { name: "Újraellenőrzés" });
  fireEvent.click(button);
  fireEvent.click(button);
  expect(await screen.findByText("A rendszer készen áll.")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("reports an unexpected response shape as invalid, not as unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ backend: "?" }))));
  render(<BackendStatus />);
  expect(await screen.findByText("A backend válasza nem értelmezhető. Próbáld újra.")).toBeTruthy();
});

test("reports a failed request as unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
  render(<BackendStatus />);
  expect(await screen.findByText("A backend nem érhető el. Próbáld újra.")).toBeTruthy();
});
