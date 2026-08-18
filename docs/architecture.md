# Architecture

## Runtime

```text
Codex -> Docker stdio MCP -> Markdown input -> deterministic PDF renderer
                                                |-> ArtifactStore
                                                |-> IdempotencyLedger
                                                `-> SimpleUploadPublisher
                                                      |-> UserTokenProvider
                                                      `-> exact-host HTTPS transport
```

The MCP has one operation. Inline text and approved-root regular files converge to one UTF-8 Markdown string. The renderer handles headings, paragraphs, emphasis, code, lists, block quotes, tables, and HTTP(S)/mailto links, then writes a deterministic content-addressed PDF before any network operation. It checks the source against the embedded fonts and rejects unsupported glyphs rather than rendering missing-glyph boxes.

The container has no listening port, Docker socket, broad host mount, or persistent user-token storage. `/artifacts` is writable, `/imports/N` is read-only, `/tmp` is ephemeral, and the named state volume stores only the device credential and SQLite successful-upload ledger.

## Publish flow

For a live publish, the service derives idempotency from the rendered PDF SHA-256 and title. A cross-process state-volume lock covers the ledger lookup, upload, and success record. A recorded success returns locally without network access. Otherwise the simple-upload adapter reads the preserved PDF and performs one `POST` to the fixed upload URL.

If state is unavailable before transport, the call fails without uploading. If the endpoint confirms delivery but the success record cannot be written, the call returns a classified state failure with the remote identifiers, `deliveryStatus=confirmed`, and `retrySafe=false`.

A recognized response must be HTTP 2xx JSON with a non-empty `docID` and a 64-character lowercase hexadecimal `hash`. Any other response fails closed with the rendered PDF preserved. The returned `docID` is exposed only because this endpoint response supplies it; the application does not invent or pre-reserve one.

## Compatibility boundary

The simple-upload endpoint is private, observed behavior—not an official publishing API. The implementation is based on pinned MIT-licensed source evidence recorded in ADR 0004. Protocol drift must fail closed with the rendered PDF preserved.
