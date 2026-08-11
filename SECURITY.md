# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately to
<aminn.zoroufi@gmail.com>. Do not include credentials, private data, or an
exploit against a system you do not own. Acknowledgement is targeted within
seven calendar days; no service-level guarantee is implied.

## Supported scope

Only the current `main` branch is maintained. This repository is a local,
low-voltage portfolio demonstrator, not a hosted service or certified control
product.

## Demo versus deployment

The local Compose profile uses isolated-network development credentials and
plain MQTT. Any real deployment must rotate all secrets, terminate TLS, use
per-device credentials or certificates, restrict broker ACLs, separate command
authorization, and complete a site-specific threat and safety review.

Never report secrets through a public issue. If a secret is accidentally
committed, revoke it before attempting history cleanup.

