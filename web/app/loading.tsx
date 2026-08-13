// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

export default function Loading() {
  return (
    <main className="centered-page" aria-live="polite">
      <div className="loading-mark" aria-hidden="true" />
      <span className="sr-only">Loading monitoring data</span>
    </main>
  );
}
