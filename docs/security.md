# Security model

## Secrets and network boundary

The device credential is stored with mode `0600` in a `0700` directory inside the named state volume. It is loaded only to exchange an in-memory user token. Pairing codes are read from interactive standard input, never arguments or environment variables.

Authentication requests are restricted to `https://webapp-prod.cloud.remarkable.engineering`. PDF upload requests are restricted to the exact URL `https://internal.cloud.remarkable.com/doc/v2/files`. Both transports disable redirects. Tokens exist only in request headers held in memory. Errors are locally generated and exclude remote bodies, headers, tokens, signed URLs, account data, and document contents.

## Markdown and artifacts

The host artifact directory defaults to a private directory beneath the process temporary root, which Codex exposes as writable in workspace-sandboxed tasks. Operators may override it only with the non-secret `REMARKABLE_ARTIFACT_HOST_DIR` option. MCP initialization and discovery do not create or access this directory. An actual publication call creates the selected directory with mode `0700`; rendered PDFs remain content-addressed and are preserved there after publication failures.

The host broker can open any path allowed by its operating-system identity, but it accesses only the exact `filePath` named in an `upload_markdown` request. It opens the final component nonblocking with `O_NOFOLLOW`, requires a regular file, reads at most 10 MB plus one byte, and returns sanitized local failures without the source path or body. The broker copies accepted bytes to a mode-`0600` file inside a mode-`0700` call-scoped temporary directory. Only that directory is mounted read-only at `/imports/0`; the original host path, parent directory, workspace, home directory, and host root are not mounted. Staged files are removed after the matching response and all remainder is removed when the one-shot call exits.

Inside the container, file inputs remain restricted to `/imports/0` as defense in depth and decode strictly as UTF-8. Markdown is escaped before the renderer applies its supported inline styles, narrow symbol fallback, and safe link schemes, so source HTML is not executed. Unsupported font glyphs fail closed. The rendered content-addressed PDF is created before transport and survives every failure.

## Container

No container runs during MCP initialization or tool discovery. A publication call may first run the existing short-lived root helper with access only to the named state volume so it can enforce credential-directory ownership and permissions. It then starts one unprivileged publisher container with a read-only root, dropped capabilities, no-new-privileges, finite resource limits, no published ports, no Docker socket, one artifact bind mount, one ephemeral read-only staging mount, the state volume, and ephemeral tmpfs. The host sends only the private handshake and single request, keeps publisher stdin open while awaiting the matching response, then closes stdin and waits for `docker run --rm` to exit. A bounded timeout terminates the ephemeral process and returns a sanitized non-retry-safe result with unknown delivery status.

The MCP tool and CLI upload command are publication-only operations; invoking either is explicit intent to upload. Tool discovery is not publication intent and does not start Docker. Unit tests use synthetic data and no network. Real-account testing requires explicit intent and synthetic content. No credential or publish-mode configuration is forwarded into Docker.
