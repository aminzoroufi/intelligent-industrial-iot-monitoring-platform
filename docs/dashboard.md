# Operator dashboard

The Next.js dashboard is a responsive operator surface for the simulated
condition-monitoring stack. It is served at `http://localhost:3000` by the
Compose `web` service and uses UTC consistently in displayed timestamps.

## Workflows

- fleet overview with online, degraded, and offline status text plus color;
- device detail with retained health, current measurements, bounded live and
  historical charts, explicit gaps, SI units, and threshold overlays;
- active and historical alarms with acknowledgement state;
- audited threshold, calibration, and maintenance changes;
- short-lived low-voltage demonstration relay commands with separate accepted,
  completed, rejected, and timed-out states;
- bounded CSV export;
- deterministic-threshold versus anomaly-model comparison driven by the model
  registry, with explicit not-ready, ready, stale, and error states plus the
  versioned synthetic metric/scenario report;
- About/legal content with authorship, source license, verification level, and
  safety boundary.

## Authentication boundary

The browser sends credentials only to the dashboard's same-origin login route.
The server-side route exchanges them with FastAPI and stores the resulting JWT
in an HttpOnly, SameSite=Strict cookie. Dashboard REST requests use an explicit
allow-listing backend-for-frontend; browser code does not read or persist the
token. Non-GET proxy requests reject a mismatched Origin when one is present.

Live updates connect directly to FastAPI because a WebSocket upgrade cannot be
proxied through a Next.js route handler. FastAPI requires an exact allowed
browser Origin and authenticates the upgrade from the same host-only HttpOnly
cookie. For local access, the client normalizes `localhost`, `127.0.0.1`, and
`::1` to the hostname of the dashboard page so the cookie scope stays aligned.
Production must use HTTPS/WSS, set `IIOT_COOKIE_SECURE=true`, and replace the
development origins and secrets.

## Rendering and data limits

Initial page reads happen in Server Components and independent requests run in
parallel. Interactive controls are isolated in Client Components. The live
chart retains at most 240 points in browser memory, creates discontinuous SVG
paths for missing samples, labels axes and units, and shows warning/critical
thresholds. Anomaly markers appear only for persisted scored rows; a model
score is never presented as a probability. The comparison route separately
shows threshold alarms, persisted model readiness, recently returned scored
rows, confusion-derived synthetic metrics, and detection delay.

## Verification boundary

ESLint, strict TypeScript compilation, four Vitest component tests, and the
Next.js production build pass. The build now self-hosts checksum-tracked Geist
subsets under SIL OFL 1.1 and succeeds without a Google Fonts request. An
earlier npm audit reported zero vulnerabilities; the latest local rerun could
not reach the registry, so CI must produce the current audit evidence. A prior
browser smoke passed sign-in, fleet rendering, console inspection, and desktop
overflow inspection. The required container rebuild and browser rerun after
the loopback normalization fix were not executed, so the cookie-authenticated
live path is recorded as blocked until it actually runs.
