# Deployment lifecycle

The old AccountContext deployment is retired. Its old-host `install.py`, app-local
deployment wrapper and bootstrap command are removed. Do not recreate these
commands or the old host credentials.

The maintained [common CI and deployment contract](../docs/ci-and-deployment.md)
is authoritative. Deployment remains explicitly disabled in this repository.
A separately authorized fresh deployment uses the `pocketdeploy-v2` scaffold's
GitHub delivery with an app-specific forced-command SSH key. The commandless
connection sends no registry credentials. PocketDeploy converges only this
application under its host lock, stops the existing writer cleanly, preserves its
volume, and health-checks the replacement. It does not automatically roll back.

See [runtime configuration and recovery](../docs/deployment.md) for required
primary-object storage, separate Litestream credentials and explicit fresh-volume
initialization. `docker/backup.py` is an offline legacy archive utility, excluded
from the current image; it is not part of the deployment or recovery entrypoint.

## Published image archives

The image workflow publishes tested AMD64 and ARM64 archives in GitHub Releases
under `image-<full-source-commit>`, with `.sha256` checksums and per-architecture
source/digest metadata. Verify the checksum before loading an archive with Docker.
Loading an image is not deployment and does not enable the retired workflow job.

Run `python3 tests/deploy_workflow.py` for isolated deployment-contract checks.
