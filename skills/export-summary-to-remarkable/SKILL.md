---
name: export-summary-to-remarkable
description: Render Markdown text or a UTF-8 text file as PDF and upload it to the reMarkable library. Use when the user asks to preview, dry-run, send, export, upload, or publish text, notes, summaries, reports, investigation results, or text files to reMarkable.
---

# Export Markdown to reMarkable

## Prepare the request

- Treat plain text and every UTF-8 text file as Markdown, regardless of filename extension.
- Use `markdownText` for content from the conversation or content already loaded into context. Use `filePath` for a local file. Pass exactly one; never pass a PDF or an artifact ID.
- Use the requested title. If omitted, infer it from the first Markdown H1, then the filename stem. Ask only when neither yields a useful title.
- Simple uploads normally land in the library root.

## Publish

1. Call `upload_markdown` with `dryRun=true`.
2. On success, report the title plus the preserved PDF artifact path and SHA-256. State clearly that nothing was uploaded.
3. If the user already said to send, upload, export, or publish now, that is explicit live intent. Otherwise ask for confirmation after the dry-run.
4. Call `upload_markdown` again with the same source and title, setting `dryRun=false` and `confirmUpload=true`.
5. Report delivery only when `ok=true`. Include the remote title, whether the result was a locally suppressed retry, any response-supplied remote document ID, and the preserved artifact path.
6. On failure, report `errorStage`, `errorCode`, the sanitized message, and the preserved artifact path. Do not claim partial or probable delivery. When `deliveryStatus=confirmed` and `retrySafe=false`, report that delivery was confirmed but local retry suppression failed, and do not retry automatically.

If a file changes after the dry-run, perform a new dry-run and treat it as a new publish intent. Exact retries require identical source content and title.

## Guardrails

- Dry-run is always the first call, including when live intent is already explicit.
- Do not select another source or output format, pass through a PDF, or reuse a generated artifact as input.
- Do not silently turn a file decoding or rendering failure into another format.
- Do not retry a result with `retrySafe=false`, even when `ok=false`.
- Never expose credentials, authorization headers, private response bodies, signed URLs, account listings, or document bodies returned by tools.
- Local idempotency cannot detect uploads made by another installation or after ledger loss.

Read [references/backends.md](references/backends.md) when configuring live mode.
