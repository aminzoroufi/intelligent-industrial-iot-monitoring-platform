// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import { NextResponse, type NextRequest } from "next/server";
import { isSameOrigin } from "@/lib/origin";

const API_URL = process.env.IIOT_API_INTERNAL_URL ?? "http://127.0.0.1:8000";
const DEVICE_ID = /^[a-z0-9][a-z0-9-]{0,62}$/;
const RECORD_ID = /^[1-9][0-9]{0,10}$/;

function requestIsAllowed(method: string, segments: string[]): boolean {
  if (method === "GET" && segments.length === 2 && segments[0] === "auth" && segments[1] === "me") {
    return true;
  }
  if (segments[0] === "devices") {
    if (method === "GET" && segments.length === 1) return true;
    if (!DEVICE_ID.test(segments[1] ?? "")) return false;
    if (method === "GET" && segments.length === 2) return true;
    if (
      method === "GET" &&
      segments.length === 3 &&
      ["telemetry", "anomaly-model", "calibrations", "maintenance", "thresholds", "commands", "export.csv"].includes(
        segments[2],
      )
    ) {
      return true;
    }
    if (
      method === "POST" &&
      segments.length === 3 &&
      ["calibrations", "maintenance"].includes(segments[2])
    ) {
      return true;
    }
    if (method === "PUT" && segments.length === 3 && segments[2] === "thresholds") return true;
    if (
      method === "POST" &&
      segments.length === 4 &&
      segments[2] === "commands" &&
      segments[3] === "relay"
    ) {
      return true;
    }
    return false;
  }
  if (
    method === "GET" &&
    segments.length === 2 &&
    segments[0] === "anomaly" &&
    segments[1] === "evaluation-demo"
  ) {
    return true;
  }
  if (segments[0] === "alarms") {
    if (method === "GET" && segments.length === 1) return true;
    return (
      method === "POST" &&
      segments.length === 3 &&
      RECORD_ID.test(segments[1] ?? "") &&
      segments[2] === "acknowledge"
    );
  }
  return (
    method === "PATCH" &&
    segments.length === 2 &&
    segments[0] === "maintenance" &&
    RECORD_ID.test(segments[1] ?? "")
  );
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!requestIsAllowed(request.method, path)) {
    return NextResponse.json({ detail: "Backend route is not allowed" }, { status: 404 });
  }
  if (!["GET", "HEAD"].includes(request.method)) {
    const origin = request.headers.get("origin");
    if (origin !== null && !isSameOrigin(origin, request.nextUrl.origin)) {
      return NextResponse.json({ detail: "Cross-origin mutation rejected" }, { status: 403 });
    }
  }
  const token = request.cookies.get("iiot_session")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  const target = new URL(`/api/v1/${path.join("/")}`, API_URL);
  target.search = request.nextUrl.search;
  const headers = new Headers({ authorization: `Bearer ${token}` });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const responseHeaders = new Headers({ "cache-control": "no-store" });
    for (const name of ["content-type", "content-disposition"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    const response = new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
    if (upstream.status === 401) response.cookies.delete("iiot_session");
    return response;
  } catch {
    return NextResponse.json({ detail: "Monitoring API unavailable" }, { status: 503 });
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
