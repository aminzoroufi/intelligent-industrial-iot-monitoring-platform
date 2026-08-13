// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="centered-page">
      <section className="auth-card" role="alert">
        <p className="eyebrow danger-text">Application error</p>
        <h1>This view could not be loaded</h1>
        <p className="muted">The failure was contained. Retry, then inspect service health if it persists.</p>
        <button className="button primary" type="button" onClick={reset}>
          Try again
        </button>
      </section>
    </main>
  );
}
