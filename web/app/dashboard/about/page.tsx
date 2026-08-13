// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return <main className="page"><header className="page-header"><div><p className="eyebrow">About / legal</p><h1>Engineering evidence, with honest boundaries.</h1><p>A portfolio-grade industrial IoT demonstrator for condition monitoring of a small workshop asset.</p></div></header>
    <div className="content-grid"><section className="panel legal-copy"><h2>Intelligent Industrial IoT Monitoring Platform</h2><p>The running dashboard connects retained device health, versioned MQTT telemetry, deterministic alarms, audit workflows, and a low-voltage simulated command path. Seeded values and the gateway are labeled simulated. No bench or field validation is implied.</p><p><strong>Author:</strong> Amin Zoroufi<br /><strong>Email:</strong> <a href="mailto:aminn.zoroufi@gmail.com">aminn.zoroufi@gmail.com</a><br /><strong>Copyright:</strong> © 2026 Amin Zoroufi. All rights reserved except as stated in the repository license.</p><p>Source is visible under the custom Portfolio Source-Available License. It is not an open-source license and remains marked for legal review.</p><div className="inline-actions"><a className="button primary" href="https://github.com/aminzoroufi/intelligent-industrial-iot-monitoring-platform">Repository</a><a className="button" href="https://github.com/aminzoroufi/intelligent-industrial-iot-monitoring-platform/blob/main/LICENSE.md">License</a></div></section>
      <aside className="content-stack"><section className="panel"><h2>Verification level</h2><p className="eyebrow">SIMULATED</p><p className="muted">Software-only evidence. Hardware remains unverified until physical results are supplied.</p></section><section className="panel"><h2>Safety boundary</h2><p className="muted">Extra-low-voltage demo only. Never use the relay as an emergency stop, interlock, or mains switch.</p></section><section className="panel"><h2>Operator routes</h2><p className="muted">Return to the <Link href="/dashboard">fleet overview</Link> or inspect <Link href="/dashboard/devices/motor-01">motor-01</Link>.</p></section></aside>
    </div>
  </main>;
}
