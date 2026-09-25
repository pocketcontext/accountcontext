# Deployment transport

The image workflow publishes tested AMD64 and ARM64 images as public GitHub Release
assets under tag `image-<full-source-commit>`. Each release contains:

- `accountcontext-linux-amd64.tar.gz` and its `.sha256` checksum file.
- `accountcontext-linux-arm64.tar.gz` and its `.sha256` checksum file.
- One `.txt` file per architecture recording source revision and registry digest.

Verify the checksum with `sha256sum --check` in the download directory, then run
`docker load --input accountcontext-linux-arm64.tar.gz` (or the AMD64 archive).
The loaded tag is `ghcr.io/pocketcontext/accountcontext:sha-<full-source-commit>`.
These image downloads are public. Anonymous GHCR manifest, configuration and ARM64
layer access were also verified on 25 September 2026. Registry visibility is independent
of source visibility; the CI transport also supports an authorized private package.

Production retains `ghcr.io/pocketcontext/accountcontext:latest` and the fixed-target
`deploy-accountcontext.py` wrapper. The wrapper accepts no command-line arguments.
Its optional standard input is one JSON object containing exactly `username` and
`token`, bounded to 16 KiB. Empty input requests an anonymous pull. GitHub Actions
supplies its job-scoped token through SSH standard input with `packages: read`.

The root-owned wrapper authenticates only to `ghcr.io`, using `docker login
--password-stdin`. Login output is captured and never emitted. Credentials reside
in a temporary Docker configuration with mode 0700; cleanup runs after success or
failure. Existing Docker credentials and sibling app configuration stay untouched.
ONCE v0.3.3 uses that temporary Docker keychain when pulling the fixed app image.
No token is persisted in ONCE settings or passed as a command-line argument.

The wrapper still acquires the AccountContext deployment lock, validates the sole
matching container and image, pulls before stopping, requires a graceful stop, and
updates only `accounts.pocketcontext.com` with automatic updates disabled. CI waits
for application/container tests and public release publication before deployment.
