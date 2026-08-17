---
name: export-summary-to-remarkable
description: Format and export concise summaries from Codex to a reMarkable tablet. Use when the user asks to send, save, publish, or export a conversation summary, research brief, meeting recap, or Markdown note to reMarkable.
---

# Export Summary to reMarkable

Create a paper-friendly Markdown summary, preview the exact content and destination, then invoke the configured export backend.

## Workflow

1. Identify the source material and intended title. Default to the current task summary.
2. Produce a concise document with a title, date, key points, decisions, and next actions when those sections apply.
3. Avoid wide tables, deeply nested lists, raw URLs, and long unbroken code blocks.
4. Ask for missing destination details only when they materially affect the result. Otherwise use the configured default folder.
5. Show the title, destination, output type, and a short content preview before the first external upload.
6. Obtain confirmation before sending unless the user's current request explicitly says to export or send now.
7. Invoke the configured backend and report the returned document identifier or a clear failure reason.

## Output types

- Prefer `notebook` when the configured backend supports editable native text.
- Use `pdf` when layout fidelity matters more than editable text.
- Never describe a PDF or EPUB as an editable notebook.

## Backend rules

- Read [references/backends.md](references/backends.md) when selecting or configuring a backend.
- Prefer a documented local or user-controlled transport.
- Treat reMarkable cloud endpoints as private and unstable unless reMarkable publishes an API contract.
- Never print, commit, or place authentication tokens in generated documents.
- Do not silently fall back from `notebook` to `pdf`; disclose the change and obtain consent.

## Failure handling

- Preserve the generated summary if conversion or upload fails.
- Make retries idempotent where the backend permits it.
- Report whether failure occurred during formatting, conversion, authentication, upload, or sync.
