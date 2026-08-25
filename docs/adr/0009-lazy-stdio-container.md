# ADR 0009: Keep MCP discovery on the host and start Docker per publication call

- Status: accepted
- Date checked: 2026-08-21

## Context

Codex starts an enabled plugin-provided stdio MCP command for each agent turn so that it can
initialize the server and discover its tools. The current launcher immediately starts a long-lived
Docker container and forwards that stdio session into it. Observed Codex desktop sessions can retain
earlier stdio commands after their turns finish, which leaves one idle publisher container per turn
even when no reMarkable tool was requested.

The public plugin contract has one statically versioned tool. Discovery does not require the device
credential, renderer, state ledger, network transport, or document source. Starting those components
before `upload_markdown` also crosses an operational boundary earlier than the explicit publication
intent requires.

## Decision

Keep the plugin transport as stdio, but terminate the Docker stdio server after each publication
call. The standard-library host launcher answers MCP initialization, ping, and tool discovery from a
static contract that is tested against the containerized server. It starts the exact versioned image
only for a valid `upload_markdown` tool call, performs an internal MCP handshake, forwards that one
call, keeps container stdin open until the matching response arrives, returns only that response,
then closes stdin and waits for `docker run --rm` to exit. A bounded missing-response path terminates
the process and reports unknown delivery as non-retry-safe.

Continue staging a requested host file into a private call-scoped directory and mounting only that
directory read-only. Inline Markdown, file contents, titles, credentials, and tokens remain absent
from Docker command arguments and environment variables. A local staging rejection returns before
Docker starts. A Docker startup or protocol failure returns a sanitized MCP tool failure and leaves
no claimed or probable delivery.

## Consequences

- Ordinary Codex turns keep only a small host Python stdio process; they do not create idle Docker
  containers or touch publisher state.
- Each actual publication pays Docker startup cost and uses an isolated container that exits after
  one response.
- The host launcher becomes responsible for a narrow MCP control-plane subset and must have offline
  protocol contract tests for initialization, discovery, errors, and one-shot response correlation.
- The tool schema exists at both sides of the boundary and must remain pinned by a contract test.
- Concurrent publications still use separate containers and remain serialized by the existing
  cross-process state-volume lock.
