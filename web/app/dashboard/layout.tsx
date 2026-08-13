// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { ReactNode } from "react";
import { Suspense } from "react";
import { DashboardShell, ShellFallback } from "@/components/dashboard-shell";

export default function DashboardLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <Suspense fallback={<ShellFallback>{children}</ShellFallback>}>
      <DashboardShell>{children}</DashboardShell>
    </Suspense>
  );
}
