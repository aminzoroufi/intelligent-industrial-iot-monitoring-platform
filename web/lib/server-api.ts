// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const API_URL = process.env.IIOT_API_INTERNAL_URL ?? "http://127.0.0.1:8000";

export async function serverApi<T>(path: string): Promise<T> {
  const token = (await cookies()).get("iiot_session")?.value;
  if (!token) redirect("/login");
  const response = await fetch(new URL(`/api/v1/${path}`, API_URL), {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 401) redirect("/login?expired=1");
  if (!response.ok) throw new Error(`Monitoring API request failed (${response.status})`);
  return (await response.json()) as T;
}
