// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import { describe, expect, it } from "vitest";
import { isSameOrigin } from "@/lib/origin";

describe("isSameOrigin", () => {
  it("accepts exact and equivalent loopback origins", () => {
    expect(isSameOrigin("http://localhost:3000", "http://localhost:3000")).toBe(true);
    expect(isSameOrigin("http://127.0.0.1:3000", "http://localhost:3000")).toBe(true);
    expect(isSameOrigin("http://127.0.0.1:3000", "http://0.0.0.0:3000")).toBe(true);
  });

  it("rejects protocol, port, host, and syntax mismatches", () => {
    expect(isSameOrigin("https://localhost:3000", "http://localhost:3000")).toBe(false);
    expect(isSameOrigin("http://localhost:3001", "http://localhost:3000")).toBe(false);
    expect(isSameOrigin("http://example.com:3000", "http://localhost:3000")).toBe(false);
    expect(isSameOrigin("not an origin", "http://localhost:3000")).toBe(false);
  });
});
