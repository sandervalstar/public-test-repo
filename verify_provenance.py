"""Fixture-only signature/policy acceptance using the official GitHub CLI verifier."""

import json
import os
import subprocess
import sys
from pathlib import Path

from ci_smoke import REPOSITORY, validate_evidence


def verify_command(image, *, commit, workflow=None):
    return [
        "gh",
        "attestation",
        "verify",
        "oci://" + image,
        "--repo",
        REPOSITORY,
        "--signer-workflow",
        workflow or f"{REPOSITORY}/.github/workflows/dadoku-build.yml",
        "--signer-digest",
        commit,
        "--source-digest",
        commit,
        "--source-ref",
        "refs/heads/main",
        "--deny-self-hosted-runners",
        "--predicate-type",
        "https://slsa.dev/provenance/v1",
        "--format",
        "json",
    ]


def verified_subject(results, image):
    name, digest = image.split("@sha256:", 1)
    if not isinstance(results, list) or not results:
        raise ValueError("Verifier must return at least one verified attestation.")
    for result in results:
        verification = result.get("verificationResult") if isinstance(result, dict) else None
        if not isinstance(verification, dict):
            raise ValueError("Invalid verification result.")
        statement = verification.get("statement")
        if (
            not isinstance(statement, dict)
            or statement.get("predicateType") != "https://slsa.dev/provenance/v1"
        ):
            raise ValueError("Verified statement must use SLSA provenance v1.")
        if any(
            isinstance(subject, dict)
            and subject.get("name") == name
            and subject.get("digest") == {"sha256": digest}
            for subject in statement.get("subject", [])
        ):
            return
    raise ValueError("Verified subject does not match the exact claimed image digest.")


def verify(image, *, commit):
    command = verify_command(image, commit=commit)
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    if len(result.stdout.encode()) > 1024 * 1024:
        raise ValueError("Verifier output exceeds 1 MiB.")
    results = json.loads(result.stdout)
    verified_subject(results, image)
    print(
        "Positive policy: signature, exact image, source commit/ref, signer workflow/digest "
        "and hosted runner verified.",
        flush=True,
    )
    for name, denied in (
        ("wrong source/signer commit", verify_command(image, commit="0" * 40)),
        (
            "wrong signer workflow",
            verify_command(
                image, commit=commit, workflow=f"{REPOSITORY}/.github/workflows/not-the-builder.yml"
            ),
        ),
    ):
        failure = subprocess.run(denied, check=False, capture_output=True, text=True, timeout=120)
        if failure.returncode == 0:
            raise ValueError(f"Negative policy unexpectedly accepted: {name}.")
        print(f"Negative policy rejected: {name}.", flush=True)
    return results


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Pass the downloaded dadoku-image.json path.")
    filename = Path(sys.argv[1])
    if filename.stat().st_size > 16384:
        raise ValueError("Image evidence exceeds 16 KiB.")
    expected = {
        "commit": os.environ["SOURCE_COMMIT"],
        "run_id": int(os.environ["SOURCE_RUN_ID"]),
        "run_attempt": int(os.environ["SOURCE_RUN_ATTEMPT"]),
    }
    image = validate_evidence(json.loads(filename.read_text()), **expected)
    verify(image, commit=expected["commit"])


if __name__ == "__main__":
    main()
