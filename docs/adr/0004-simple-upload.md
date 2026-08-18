# ADR 0004: Use the observed simple-upload endpoint

- Status: accepted, experimental
- Date checked: 2026-08-18

## Context

The plugin needs a narrow transport for importing one rendered PDF. reMarkable has not documented the endpoint as an official publishing API. A pinned MIT-licensed `rmapi-js` source revision demonstrates the import operation used by the native browser extension:

- Source: https://github.com/erikbrinkman/rmapi-js/blob/c4dc999c22c62e626d7fc740b44e7f82c0b2469e/src/raw.ts
- Method and URL: `POST https://internal.cloud.remarkable.com/doc/v2/files`
- Body: raw PDF bytes
- Headers: `Content-Type: application/pdf`, base64-encoded JSON `{"file_name": title}` in `rm-meta`, `rm-source: RoR-Browser`, and the in-memory bearer token
- Recognized response: JSON `docID` and `hash`

## Decision

Upload the preserved rendered PDF through `SimpleUploadPublisher` behind the publisher boundary. Restrict transport to the exact HTTPS URL and disable redirects. Treat only HTTP 2xx JSON with a non-empty `docID` and a 64-character lowercase hexadecimal `hash` as success.

Uploads normally land in the reMarkable library root.

Derive the idempotency key from rendered PDF SHA-256 and title. Serialize the lookup, upload, and record sequence with a cross-process lock in the state volume. Record recognized successes locally and suppress an exact retry without network access. This local ledger cannot detect uploads from another installation or after ledger loss.

Fail before transport when idempotency state is unavailable. If delivery is confirmed but its success record cannot be written, return the response-supplied identifiers with a classified state failure, `deliveryStatus=confirmed`, and `retrySafe=false` so callers do not create a duplicate automatically.

## Consequences

- A live call performs one simple-upload operation in the normal success case.
- A response-supplied `docID` may be reported.
- The endpoint may drift without notice. Failures preserve the rendered PDF and expose no remote body, token, or document content.
