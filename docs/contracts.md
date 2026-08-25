# Contracts

## MCP transport

The server uses stdio and exposes exactly one tool: `upload_markdown`. The standard-library host process answers initialization, ping, and tool discovery without starting Docker. MCP protocol frames are the only standard output. Results and diagnostics must never contain credentials, authorization headers, private response bodies, signed URLs, account listings, or Markdown document bodies.

The Codex plugin bundles the server launch declaration in the supported `.mcp.json` `mcpServers` map and includes the agent-facing workflow. Codex resolves the declared `cwd` against the installed plugin root and invokes the checked-in launcher with the host's `python3`; no separately registered MCP endpoint or credential value is part of the package. Discovery does not require Docker, the image, a writable artifact directory, or access to the credential volume.

For an `upload_markdown` call, the launcher requires the contract-versioned `remarkable-codex-mcp:0.3.0` image, prepares the artifact and state locations, and runs a hardened `--rm` container for one internal MCP session. Unless explicitly overridden with `REMARKABLE_ARTIFACT_HOST_DIR`, preserved PDFs are stored below the process temporary root. A `filePath` request is replaced with an opaque staged path before it enters the container. The host keeps container stdin open until it receives the response matching the caller's JSON-RPC ID, then closes stdin and waits for the container to exit before accepting the next request on that stdio session.

When Codex defers plugin tools, the workflow must perform one exact `upload_markdown` tool search before classifying the bundled server as unavailable. A matching namespaced MCP tool is the same publication operation and must be called under the contract below.

### `upload_markdown`

Inputs: exactly one of `markdownText` or `filePath`, plus `title`. The operation has no render-only, mode-selection, or confirmation parameters; invoking it is explicit publication intent.

- `markdownText` is used verbatim as the Markdown source.
- `filePath` may identify any regular file readable by the host launcher. No configured import root is required. The broker rejects final-component symlinks, non-regular files, unreadable files, and files larger than 10 MB before forwarding the call. It copies only the requested bytes to a mode-`0600` file in private ephemeral staging, forwards only an opaque `/imports/0` path, and deletes the staged source after the matching response or call exit. The file extension does not select behavior; its contents are decoded strictly as UTF-8 Markdown inside the container.
- Empty input and input larger than 10 MB are rejected.
- Common directional arrows are rendered with the PDF Symbol font. Other source characters unavailable in the renderer font set are rejected with code points only; document content is not echoed.
- HTTP(S) and mailto Markdown links are rendered as PDF links. Unsupported link schemes remain literal text.
- Every accepted source is rendered to PDF and preserved before publication is attempted.

A success is returned only after a recognized simple-upload response and a durable local success record, or after an exact retry is found in that record. `remoteDocumentId` and `remoteHash` reflect fields returned by the response; they are not locally invented. Concurrent calls are serialized through local state. An exact retry after recorded success sets `idempotencyReplay=true` and performs no upload.

If the remote response confirms delivery but the local success record fails, the result has `ok=false`, stage `state`, code `idempotency-record-failed`, `deliveryStatus=confirmed`, `retrySafe=false`, the response-supplied remote fields, and the preserved artifact fields. Callers must not retry it automatically.

## Errors

Stable stages include `input`, `configuration`, `authentication`, `upload`, and `state`. Stable codes include `invalid-publish-request`, `docker-launch-failed`, `docker-protocol-failed`, `simple-upload-unavailable`, `credential-missing`, `private-authentication-failed`, `simple-upload-failed`, `simple-upload-response-unrecognized`, `idempotency-state-unavailable`, and `idempotency-record-failed`.

Failure results remain locally generated and include the preserved artifact fields whenever rendering completed.

Host staging failures use stage `input` and code `invalid-publish-request`. They contain no source path or document content and mean no container publication was attempted.

Docker startup and internal MCP response-correlation failures use stage `configuration` and the codes `docker-launch-failed` and `docker-protocol-failed`. Their messages are locally generated, contain no subprocess details or document content, and never claim delivery. Because a lost response cannot prove whether transport started, `docker-protocol-failed` includes `deliveryStatus=unknown` and `retrySafe=false`; callers must not retry it automatically.

## Idempotency limitation

The key is SHA-256 over the normalized title and rendered PDF SHA-256. Only recognized successes are recorded. Local suppression cannot detect uploads performed by another installation or uploads whose ledger entry was lost.
