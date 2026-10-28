# Dadoku public signed-provenance acceptance fixture

This repository contains only a synthetic, stateless HTTP app and acceptance tests.
It is a disposable public fixture, not a production deployment or a trust policy
for arbitrary repositories. No real credentials or private application data belong here.

Run `python3 -m unittest -v` locally. The app uses the Python standard library.
The pinned non-root Docker image serves `/`, `/healthz`, HEAD and JSON 404 responses.

The build workflow is derived from Dadoku's generated workflow, with explicit
fixture-only extensions:

- The publishing job has Contents read, Packages write, Attestations write and
  ID-token write. Test and verification jobs do not get those write permissions.
- After tests and image publication, a commit-pinned official GitHub attestation
  action signs the exact image digest and pushes the attestation to GHCR.
  Linked-artifact storage-record creation is disabled; no extra metadata grant.
- A separate read-only workflow checks the exact successful source run/attempt,
  verifies the OCI image's attestation using GitHub CLI, pins repository, source
  digest/ref, signer workflow/digest and GitHub-hosted runners, and exercises
  negative source/workflow checks.
- Only after verification succeeds does the container smoke test pull/run the
  exact digest, check source labels/non-root/platform, constrain the container,
  test health/HTTP behavior and confirm clean SIGTERM/cleanup.

The unverified image-claim JSON is an input to verification, not a substitute for
signature validation. A valid attestation links an image to its source/workflow;
it does not establish that the source is safe or authorize a production deployment.
The separate verification workflow is acceptance scaffolding, not an assertion
that Dadoku's server-side automatic provenance verification is implemented.
This fixture exercises an optional stronger trust tier. Dadoku must also support
private repositories without Enterprise or GitHub attestations; this workflow is
not a mandatory template or a prerequisite for explicit exact-digest deployments.
