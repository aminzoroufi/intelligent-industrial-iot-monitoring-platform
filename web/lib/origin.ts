// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "0.0.0.0", "::"]);

function effectivePort(url: URL): string {
  if (url.port) return url.port;
  if (url.protocol === "https:") return "443";
  if (url.protocol === "http:") return "80";
  return "";
}

export function isSameOrigin(candidate: string, expected: string): boolean {
  try {
    const candidateUrl = new URL(candidate);
    const expectedUrl = new URL(expected);
    if (
      candidateUrl.protocol !== expectedUrl.protocol ||
      effectivePort(candidateUrl) !== effectivePort(expectedUrl)
    ) {
      return false;
    }
    if (candidateUrl.hostname === expectedUrl.hostname) return true;
    return LOOPBACK_HOSTS.has(candidateUrl.hostname) && LOOPBACK_HOSTS.has(expectedUrl.hostname);
  } catch {
    return false;
  }
}
