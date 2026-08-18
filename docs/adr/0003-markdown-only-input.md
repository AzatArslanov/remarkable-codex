# ADR 0003: Use one Markdown input contract

- Status: accepted
- Date: 2026-08-18

## Decision

Expose one MCP operation, `upload_markdown`, accepting exactly one inline Markdown string or approved-root UTF-8 file. Treat file contents as Markdown regardless of extension. Render every accepted source to a deterministic, content-addressed PDF and pass only that artifact to the existing publisher boundary.

Operational status is available through the local `doctor` command.

## Consequences

The public workflow has one source type and one rendering path. Exact retries can regenerate the same PDF and derive the same idempotency key without accepting a managed artifact as input. The PDF remains available for preview and manual recovery after transport failure.
