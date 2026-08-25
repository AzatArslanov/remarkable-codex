# ADR 0008: Version the bundled MCP image contract

- Status: accepted
- Date checked: 2026-08-19

## Context

The Codex plugin launches a locally built Docker image. The MCP schema and publication semantics
changed incompatibly when the render-only parameters were removed. Reusing the previous image tag
could therefore start an older server that reports a successful dry-run to a publication-only
caller.

The plugin's `.mcp.json` must also use a bundled-server shape accepted by Codex plugin ingestion.
The plugin validator requires the standard `mcpServers` wrapper around the server map.

## Decision

Version `0.3.0` is the shared contract version for the plugin manifest, Python distribution,
launcher default image, Docker image metadata, and operator build command. Breaking MCP schema or
publication-semantics changes require a new versioned image tag. The launcher does not fall back to
an older tag.

The bundled `.mcp.json` has one top-level `mcpServers` object whose sole server key is
`remarkable-publisher`.

## Consequences

- An existing `remarkable-codex-mcp:0.2.0` image cannot silently serve the `0.3.0` plugin.
- Operators must build the exact image tag documented for the installed plugin.
- Offline contract tests keep package, plugin, launcher, image metadata, and documentation versions
  aligned.
