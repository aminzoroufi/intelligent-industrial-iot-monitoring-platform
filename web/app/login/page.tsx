// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-intro" aria-labelledby="platform-title">
        <div className="brand-mark" aria-hidden="true">
          <span />
        </div>
        <p className="eyebrow">Workshop demo / motor-01</p>
        <h1 id="platform-title">Condition intelligence for the maintenance floor.</h1>
        <p>
          One bounded, transparent view of temperature, vibration, current, alarms, and device
          health—built for a simulated low-voltage demonstrator.
        </p>
        <ul className="login-signals" aria-label="Monitored signals">
          <li>Temperature</li>
          <li>Vibration RMS</li>
          <li>DC current</li>
        </ul>
      </section>
      <section className="auth-card" aria-labelledby="sign-in-title">
        <div className="simulation-banner">SIMULATED DATA · NOT A SAFETY CONTROLLER</div>
        <p className="eyebrow">Operator access</p>
        <h2 id="sign-in-title">Sign in to the monitor</h2>
        <p className="muted">Use the local demonstration account configured by the stack.</p>
        <Suspense fallback={<div className="form-skeleton" aria-label="Loading sign-in form" />}>
          <LoginForm />
        </Suspense>
        <p className="legal-small">
          Extra-low-voltage demonstration only. Commands must never replace physical isolation.
        </p>
      </section>
    </main>
  );
}
