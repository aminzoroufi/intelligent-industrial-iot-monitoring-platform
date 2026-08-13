// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import Link from "next/link";

export default function NotFound() {
  return (
    <main className="centered-page">
      <section className="auth-card">
        <p className="eyebrow">404</p>
        <h1>View not found</h1>
        <p className="muted">The requested operator view does not exist.</p>
        <Link className="button primary" href="/dashboard">
          Return to fleet
        </Link>
      </section>
    </main>
  );
}
