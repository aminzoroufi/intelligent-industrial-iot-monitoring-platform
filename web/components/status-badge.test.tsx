// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { StatusBadge } from "@/components/status-badge";

it("exposes device state as text and not color alone", () => {
  render(<StatusBadge status="degraded" />);
  expect(screen.getByText("degraded")).toBeVisible();
});
