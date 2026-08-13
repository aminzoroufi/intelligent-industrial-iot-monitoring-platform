// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { DeviceStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: DeviceStatus | string }) {
  return (
    <span className={`status-badge ${status}`}>
      <span className={`status-dot ${status}`} aria-hidden="true" />
      {status.replaceAll("_", " ")}
    </span>
  );
}
