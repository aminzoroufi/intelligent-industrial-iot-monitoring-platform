// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import { expect, test } from "@playwright/test";

test("operator signs in, inspects live asset, and forces demo relay off", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in to the monitor" })).toBeVisible();
  await page.getByLabel("Password").fill("local-demo-admin-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Asset condition, without the noise." })).toBeVisible();
  await page.getByRole("link", { name: /Workshop demo motor/ }).click();

  await expect(page.getByRole("heading", { name: "Workshop demo motor" })).toBeVisible();
  await expect(page.getByRole("img", { name: /Temperature history/ })).toBeVisible();
  const commandResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" && response.url().includes("/commands/relay"),
  );
  await page.getByRole("button", { name: "Force OFF" }).click();
  expect((await commandResponse).ok()).toBe(true);
  await expect(page.getByText("RELAY_OFF").first()).toBeVisible({ timeout: 15_000 });
});
