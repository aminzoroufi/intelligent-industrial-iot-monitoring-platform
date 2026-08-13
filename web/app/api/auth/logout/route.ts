// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set("iiot_session", "", {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.IIOT_COOKIE_SECURE === "true",
    path: "/",
    expires: new Date(0),
  });
  return response;
}
