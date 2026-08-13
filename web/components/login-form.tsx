// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const expired = searchParams.get("expired") === "1";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ username: data.get("username"), password: data.get("password") }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail ?? "Sign-in failed");
      }
      const requested = searchParams.get("returnTo");
      const destination = requested?.startsWith("/dashboard") ? requested : "/dashboard";
      router.replace(destination);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="stack-form" onSubmit={submit}>
      {expired ? <div className="notice warning">Your session expired. Sign in again.</div> : null}
      {error ? (
        <div className="notice danger" role="alert">
          {error}
        </div>
      ) : null}
      <label>
        <span>Username</span>
        <input name="username" autoComplete="username" defaultValue="demo-admin" required maxLength={80} />
      </label>
      <label>
        <span>Password</span>
        <input name="password" type="password" autoComplete="current-password" required maxLength={512} />
      </label>
      <button className="button primary wide" disabled={submitting} type="submit">
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
