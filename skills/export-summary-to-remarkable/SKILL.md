---
name: export-summary-to-remarkable
description: Render Markdown text or a UTF-8 text file as PDF and upload it to the reMarkable library. Use when the user asks to send, export, upload, or publish text, notes, summaries, reports, investigation results, or text files to reMarkable.
---

# Export Markdown to reMarkable

## Bundled MCP tool

- Use the plugin's bundled `upload_markdown` tool.
- If it is not directly visible, search for the exact tool name `upload_markdown` once and use the matching namespaced MCP tool returned by that search.
- Do not start or authenticate the MCP server as part of an export request.
- Only report the bundled MCP server unavailable after the exact tool search returns no match. Then suggest checking that the `remarkable-codex` plugin and its bundled MCP server are installed and enabled. Docker is not required for tool discovery. Do not substitute another transport.

## Prepare the request

- Treat plain text and every UTF-8 text file as Markdown, regardless of filename extension.
- Use `markdownText` for content already present in the conversation. Use `filePath` for any host-readable regular file, including files outside the current workspace; the local broker stages only the requested file. Pass exactly one; never pass a PDF or an artifact ID.
- Use the requested title. If omitted, infer it from the first Markdown H1, then the filename stem. Ask only when neither yields a useful title.
- Simple uploads normally land in the library root.

## Publish

1. Treat the user's request to send, export, upload, or publish as explicit publication intent.
2. Call `upload_markdown` once with the source and title. The tool has no preview or mode switches.
3. Report delivery only when `ok=true`. Include the remote title, whether the result was a locally suppressed retry, any response-supplied remote document ID, and the preserved artifact path.
4. On failure, report `errorStage`, `errorCode`, the sanitized message, and the preserved artifact path. Do not claim partial or probable delivery. When `deliveryStatus=confirmed` and `retrySafe=false`, report that delivery was confirmed but local retry suppression failed, and do not retry automatically.

For `docker-launch-failed` or `docker-protocol-failed`, report that publication was not verified and suggest checking Docker plus the exact local `remarkable-codex-mcp:0.3.0` image. Treat `docker-protocol-failed` as `deliveryStatus=unknown` and `retrySafe=false`; do not retry it automatically. After a local correction, retry only when the user explicitly asks, relying on the content-derived ledger to suppress a previously recorded success.

Exact retries require identical source content and title.

## Guardrails

- Do not call the tool merely to preview content; every accepted call attempts publication.
- Do not select another source or output format, pass through a PDF, or reuse a generated artifact as input.
- Do not silently turn a file decoding or rendering failure into another format.
- Do not replace unsupported characters with lookalikes or ASCII approximations; report the renderer error without modifying the source.
- Do not broaden Docker mounts or copy a file manually to an import directory; pass its original path in `filePath` and let the broker stage it.
- Do not retry a result with `retrySafe=false`, even when `ok=false`.
- Never expose credentials, authorization headers, private response bodies, signed URLs, account listings, or document bodies returned by tools.
- Local idempotency cannot detect uploads made by another installation or after ledger loss.

Read [references/backends.md](references/backends.md) for transport compatibility and failure handling.
