// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import { NextResponse, type NextRequest } from "next/server";

const API_URL = process.env.IIOT_API_INTERNAL_URL ?? "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }
  const username =
    typeof body === "object" && body !== null && "username" in body
      ? String(body.username).trim()
      : "";
  const password =
    typeof body === "object" && body !== null && "password" in body
      ? String(body.password)
      : "";
  if (!username || username.length > 80 || password.length < 1 || password.length > 512) {
    return NextResponse.json({ detail: "Username and password are required" }, { status: 422 });
  }

  const form = new URLSearchParams({ username, password });
  try {
    const upstream = await fetch(`${API_URL}/api/v1/auth/token`, {
      method: "POST",
      body: form,
      headers: { "content-type": "application/x-www-form-urlencoded" },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!upstream.ok) {
      return NextResponse.json(
        { detail: upstream.status === 401 ? "Incorrect username or password" : "Sign-in failed" },
        { status: upstream.status === 401 ? 401 : 502 },
      );
    }
    const token = (await upstream.json()) as {
      access_token: string;
      expires_in_s: number;
    };
    const response = NextResponse.json({ authenticated: true });
    response.cookies.set("iiot_session", token.access_token, {
      httpOnly: true,
      sameSite: "strict",
      secure: process.env.IIOT_COOKIE_SECURE === "true",
      path: "/",
      maxAge: token.expires_in_s,
    });
    return response;
  } catch {
    return NextResponse.json({ detail: "Monitoring API unavailable" }, { status: 503 });
  }
}
