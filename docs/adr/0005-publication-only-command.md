# ADR 0005: Make upload commands publication-only

- Status: accepted
- Date checked: 2026-08-18

## Context

The previous MCP and CLI contracts exposed render-only defaults plus separate live-mode and confirmation switches. The product now requires every upload command to publish, so retaining those switches would create ambiguous calls that appear to upload but stop after rendering.

The upload endpoint remains private, observed behavior rather than an official reMarkable publishing API. This decision changes command semantics, not the transport compatibility claim.

## Decision

`upload_markdown` accepts only a title and exactly one Markdown source. The CLI `upload` command likewise has no mode or confirmation flags. Invoking either publication-only command is the explicit user intent boundary. The service always renders and preserves the content-addressed PDF before attempting the `Publisher` transport.

Backend selection and experimental opt-in configuration are removed. Authentication, idempotency, classified failures, artifact preservation, and the `Publisher` abstraction remain unchanged.

## Consequences

- A successful new request always represents confirmed remote delivery; a successful exact replay represents a locally recorded prior delivery.
- Preview requests must not invoke the upload tool because it has no render-only behavior.
- Offline tests inject a fake `Publisher`; unit tests never use a network or real account.
- Existing configuration containing removed mode keys fails explicitly instead of silently changing behavior.

## Evidence checked

- Product direction supplied by the repository owner on 2026-08-18.
- Transport compatibility and source evidence remain recorded in ADR 0004.
