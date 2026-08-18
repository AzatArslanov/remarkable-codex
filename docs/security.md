# Security model

## Secrets and network boundary

The device credential is stored with mode `0600` in a `0700` directory inside the named state volume. It is loaded only to exchange an in-memory user token. Pairing codes are read from interactive standard input, never arguments or environment variables.

Authentication requests are restricted to `https://webapp-prod.cloud.remarkable.engineering`. PDF upload requests are restricted to the exact URL `https://internal.cloud.remarkable.com/doc/v2/files`. Both transports disable redirects. Tokens exist only in request headers held in memory. Errors are locally generated and exclude remote bodies, headers, tokens, signed URLs, account data, and document contents.

## Markdown and artifacts

File inputs resolve through approved read-only roots; traversal, symlink escape, and non-regular files are rejected. Files are opened nonblocking, bounded to 10 MB, and decoded strictly as UTF-8. Markdown is escaped before the renderer applies its supported inline styles and safe link schemes, so source HTML is not executed. Unsupported font glyphs fail closed. The rendered content-addressed PDF is created before live transport and survives every failure.

## Container

The container runs unprivileged with a read-only root, dropped capabilities, no-new-privileges, finite resource limits, no published ports, no Docker socket, one artifact bind mount, narrow read-only import mounts, a state volume, and ephemeral tmpfs.

Simple upload is experimental and disabled by default. Unit tests use synthetic data and no network. Live testing requires explicit intent and synthetic content. Only the non-secret backend and experimental gate are forwarded into Docker.
