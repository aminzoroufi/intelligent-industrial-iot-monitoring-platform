// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

const navigation = [
  ["Fleet", "/dashboard"],
  ["Asset", "/dashboard/devices/motor-01"],
  ["Alarms", "/dashboard/alarms"],
  ["Calibration", "/dashboard/calibration"],
  ["Maintenance", "/dashboard/maintenance"],
  ["Detection", "/dashboard/comparison"],
  ["About", "/dashboard/about"],
] as const;

export function ShellFallback({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-hidden="true" />
      <div className="app-main">{children}</div>
    </div>
  );
}

export function DashboardShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark compact" aria-hidden="true">
            <span />
          </div>
          <div>
            <strong>Workshop Monitor</strong>
            <span>Condition intelligence</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          {navigation.map(([label, href]) => {
            const active = href === "/dashboard" ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={active ? "active" : ""}
                onClick={() => setMenuOpen(false)}
              >
                <span className="nav-glyph" aria-hidden="true">
                  {label.slice(0, 1)}
                </span>
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="simulation-chip">SIMULATED</div>
          <p>Low-voltage demonstrator</p>
          <button className="text-button" type="button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="app-main">
        <header className="mobile-header">
          <button
            className="menu-button"
            type="button"
            aria-label="Toggle navigation"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((value) => !value)}
          >
            <span />
            <span />
            <span />
          </button>
          <strong>Workshop Monitor</strong>
          <span className="simulation-chip">SIM</span>
        </header>
        {children}
      </div>
      {menuOpen ? (
        <button className="menu-scrim" type="button" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />
      ) : null}
    </div>
  );
}
