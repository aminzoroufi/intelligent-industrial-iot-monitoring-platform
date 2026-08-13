// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useEffect, useEffectEvent, useState } from "react";
import type { LiveEvent } from "@/lib/types";

export type LiveState = "connecting" | "live" | "offline";

function socketUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    const configured = new URL(process.env.NEXT_PUBLIC_WS_URL);
    const loopbackNames = new Set(["localhost", "127.0.0.1", "::1"]);
    if (loopbackNames.has(configured.hostname) && loopbackNames.has(window.location.hostname)) {
      configured.hostname = window.location.hostname;
    }
    return `${configured.toString().replace(/\/$/, "")}/api/v1/ws`;
  }
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${window.location.hostname}:8000/api/v1/ws`;
}

export function useLiveSocket(onEvent: (event: LiveEvent) => void): LiveState {
  const [state, setState] = useState<LiveState>("connecting");
  const handleEvent = useEffectEvent(onEvent);

  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (stopped) return;
      setState("connecting");
      socket = new WebSocket(socketUrl());
      socket.addEventListener("open", () => setState("live"));
      socket.addEventListener("message", (message) => {
        try {
          const event = JSON.parse(String(message.data)) as LiveEvent;
          if (event.type !== "connected") handleEvent(event);
        } catch {
          // Ignore malformed server messages and keep the established connection.
        }
      });
      socket.addEventListener("close", () => {
        if (stopped) return;
        setState("offline");
        reconnectTimer = setTimeout(connect, 3000);
      });
      socket.addEventListener("error", () => socket?.close());
    };

    connect();
    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return state;
}
