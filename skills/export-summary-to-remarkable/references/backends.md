# Upload transport

Use `upload_markdown`.

MCP initialization and tool discovery run in the standard-library host control plane and do not start Docker. Calling `upload_markdown` starts a one-shot hardened container, forwards one publication request, keeps stdin open until the matching response, and then waits for container exit.

`simple-upload` posts one PDF to the private observed import endpoint. Calling `upload_markdown` is explicit upload intent; there is no render-only backend or confirmation parameter. A stored device credential is required.

The endpoint is observed behavior, not an official publishing API. Uploads normally land in the library root. Success requires HTTP 2xx JSON containing a non-empty `docID` and a valid 64-character lowercase hexadecimal `hash`. Authentication, transport, or response-validation failures must be classified and leave the rendered PDF available.

The local ledger and state-volume lock suppress exact successful retries using the rendered PDF SHA-256 and title. They cannot detect uploads made by another installation or after ledger loss. A result with `deliveryStatus=confirmed` and `retrySafe=false` means the endpoint confirmed delivery but the local success record failed; do not retry it automatically.
