# Architecture

## Runtime

```text
Codex plugin -> host stdio MCP control plane
                    |-> initialize / ping / tools/list (no Docker)
                    `-> upload_markdown
                           |-> requested file only -> call-scoped read-only staging mount
                           `-> one-shot Docker stdio MCP -> deterministic PDF renderer
                                                          |-> ArtifactStore
                                                          |-> IdempotencyLedger
                                                          `-> SimpleUploadPublisher
                                                                |-> UserTokenProvider
                                                                `-> exact-host HTTPS transport
```

The Codex plugin contains the export skill and a root-level `.mcp.json` `mcpServers` map. Its plugin-relative working directory lets Codex invoke the standard-library host control plane directly from the installed package without relying on a separately installed console script. The host process answers the narrow MCP initialization, ping, and tool-discovery surface from the versioned static contract. This allows Codex to discover `upload_markdown` without Docker access, publisher state, or an idle container.

An actual `upload_markdown` request starts the exact contract-versioned local image (`remarkable-codex-mcp:0.3.0`), performs a private MCP handshake, forwards that one request, and keeps stdin open while it waits for the correlated response. After receiving that response, or after a bounded protocol failure, it closes stdin and waits for `docker run --rm` to exit. The wrapper stores artifacts beneath the process temporary root by default, which is writable in Codex's workspace sandbox, while allowing an explicit writable `REMARKABLE_ARTIFACT_HOST_DIR` override. Breaking MCP contract changes require a new image tag; the launcher does not fall back to an older contract.

Codex may expose that operation only through deferred tool search. The agent workflow searches once for the exact `upload_markdown` name when it is not directly visible and uses the returned namespaced MCP tool. A missing direct tool entry alone is not treated as server-start failure.

The MCP has one publishing operation and no render-only mode. Inline text and host-readable regular files converge to one UTF-8 Markdown string. For a `filePath` tool call, the broker opens the exact requested host file nonblocking and without following a final-component symlink, bounds the copy to 10 MB, and writes it mode `0600` under a private call-scoped temporary directory. It replaces the host path in the forwarded MCP request with an opaque path under `/imports/0`; neither the original path nor the document body enters the Docker command or environment. Dual-source requests and invalid staging requests return locally without starting Docker or forwarding private inputs. The renderer handles headings, paragraphs, emphasis, code, lists, block quotes, tables, and HTTP(S)/mailto links, then writes a deterministic content-addressed PDF before the required publication attempt. It uses a narrow Symbol fallback for common directional arrows, checks all other source characters against the renderer font set, and rejects unsupported glyphs rather than rendering missing-glyph boxes.

The one-shot container has no listening port, Docker socket, broad host mount, or persistent user-token storage. `/artifacts` is writable, `/imports/0` is the ephemeral staging directory mounted read-only, `/tmp` is ephemeral, and the named state volume stores only the device credential and SQLite successful-upload ledger. The broker removes a staged source after the matching JSON-RPC response and removes any remainder when the call exits.

## Publish flow

For every accepted publish request, the service derives idempotency from the rendered PDF SHA-256 and title. A cross-process state-volume lock covers the ledger lookup, upload, and success record. A recorded success returns locally without network access. Otherwise the simple-upload adapter reads the preserved PDF and performs one `POST` to the fixed upload URL.

If state is unavailable before transport, the call fails without uploading. If the endpoint confirms delivery but the success record cannot be written, the call returns a classified state failure with the remote identifiers, `deliveryStatus=confirmed`, and `retrySafe=false`.

A recognized response must be HTTP 2xx JSON with a non-empty `docID` and a 64-character lowercase hexadecimal `hash`. Any other response fails closed with the rendered PDF preserved. The returned `docID` is exposed only because this endpoint response supplies it; the application does not invent or pre-reserve one.

## Compatibility boundary

The simple-upload endpoint is private, observed behavior—not an official publishing API. The implementation is based on pinned MIT-licensed source evidence recorded in ADR 0004. Protocol drift must fail closed with the rendered PDF preserved.
