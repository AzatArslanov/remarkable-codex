# Backend selection

Use `upload_markdown`.

- `dry-run` renders and preserves the PDF without network access.
- `simple-upload` posts one PDF to the private observed import endpoint and requires `REMARKABLE_EXPERIMENTAL_SIMPLE_UPLOAD=1`, a stored device credential, explicit live intent, and `confirmUpload=true`.

The endpoint is observed behavior, not an official publishing API. Uploads normally land in the library root. Success requires HTTP 2xx JSON containing a non-empty `docID` and a valid 64-character lowercase hexadecimal `hash`. Authentication, transport, or response-validation failures must be classified and leave the rendered PDF available.

The local ledger and state-volume lock suppress exact successful retries using the rendered PDF SHA-256 and title. They cannot detect uploads made by another installation or after ledger loss. A result with `deliveryStatus=confirmed` and `retrySafe=false` means the endpoint confirmed delivery but the local success record failed; do not retry it automatically.
