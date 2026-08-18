# Contracts

## MCP transport

The server uses stdio and exposes exactly one tool: `upload_markdown`. MCP protocol frames are the only standard output. Results and diagnostics must never contain credentials, authorization headers, private response bodies, signed URLs, account listings, or Markdown document bodies.

### `upload_markdown`

Inputs: exactly one of `markdownText` or `filePath`, plus `title`, `dryRun=true`, and `confirmUpload=false`.

- `markdownText` is used verbatim as the Markdown source.
- `filePath` must resolve to a regular file inside an approved import root and decode as UTF-8. Its extension does not select behavior; its contents are Markdown.
- Empty input and input larger than 10 MB are rejected.
- Source characters unavailable in the embedded PDF fonts are rejected with code points only; document content is not echoed.
- HTTP(S) and mailto Markdown links are rendered as PDF links. Unsupported link schemes remain literal text.
- Every accepted source is rendered to PDF and preserved before a live upload is attempted.
- A live call requires both `dryRun=false` and `confirmUpload=true`.

A successful dry-run result includes the title, content-derived idempotency key, replay flag, and the PDF artifact ID, path, MIME type, byte size, and SHA-256. It states that no upload occurred.

A live success is returned only after a recognized simple-upload response and a durable local success record. `remoteDocumentId` and `remoteHash` reflect fields returned by that response; they are not locally invented. Concurrent live calls are serialized through local state. An exact retry after recorded success sets `idempotencyReplay=true` and performs no upload.

If the remote response confirms delivery but the local success record fails, the result has `ok=false`, stage `state`, code `idempotency-record-failed`, `deliveryStatus=confirmed`, `retrySafe=false`, the response-supplied remote fields, and the preserved artifact fields. Callers must not retry it automatically.

## Errors

Stable stages include `input`, `configuration`, `authentication`, `upload`, and `state`. Stable codes include `invalid-publish-request`, `confirmation-required`, `simple-upload-disabled`, `simple-upload-unavailable`, `credential-missing`, `private-authentication-failed`, `simple-upload-failed`, `simple-upload-response-unrecognized`, `idempotency-state-unavailable`, and `idempotency-record-failed`.

Failure results remain locally generated and include the preserved artifact fields whenever rendering completed.

## Idempotency limitation

The key is SHA-256 over the normalized title and rendered PDF SHA-256. Only recognized successes are recorded. Local suppression cannot detect uploads performed by another installation or uploads whose ledger entry was lost.
