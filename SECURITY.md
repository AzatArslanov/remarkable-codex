# Security policy

## Supported versions

This project is pre-1.0. Security fixes are applied to the latest release and the default branch only.

| Version | Supported |
| --- | --- |
| `0.3.x` | Yes |
| `< 0.3` | No |

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/AzatArslanov/remarkable-codex/security/advisories/new). If that form is unavailable, open a public issue containing only a request for a private contact channel; do not include technical exploit details.

Never include any of the following in a report, issue, test, screenshot, or log:

- device credentials, pairing codes, bearer tokens, or authorization headers
- signed URLs, private response bodies, or account listings
- private Markdown, rendered PDFs, document titles, or host paths
- a live idempotency database or Docker state volume

Synthetic reproductions are preferred. State whether a finding affects the host broker, container boundary, renderer, authentication exchange, upload transport, or local idempotency ledger.

## Scope and expectations

High-priority reports include credential exposure, broad host mounts, source-path or document-body leakage, publication without explicit intent, unsafe retry behavior after uncertain delivery, and silent format downgrade.

The upload endpoint is private observed behavior, not an official reMarkable publishing API. Endpoint drift and entitlement changes are compatibility issues unless they expose data, bypass an intent boundary, or weaken a documented security guarantee.

The project will acknowledge a complete private report as soon as practical, investigate without requesting real credentials or private documents, and coordinate disclosure after a fix is available.
