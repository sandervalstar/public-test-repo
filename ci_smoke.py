"""Acceptance checks for this disposable repository, not a deployment trust policy."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

REPOSITORY = "sandervalstar/public-test-repo"


def validate_evidence(document, *, commit, run_id, run_attempt):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid expected commit.")
    if any(type(value) is not int or value < 1 for value in (run_id, run_attempt)):
        raise ValueError("Invalid expected run identity.")
    if not isinstance(document, dict):
        raise ValueError("Evidence must be an object.")
    image = document.get("image")
    if not isinstance(image, str) or not re.fullmatch(
        rf"ghcr\.io/{re.escape(REPOSITORY)}@sha256:[0-9a-f]{{64}}", image
    ):
        raise ValueError("Evidence must identify this repository's image by exact digest.")
    expected = {
        "version": 1,
        "repository": REPOSITORY,
        "commit_sha": commit,
        "ref": "refs/heads/main",
        "workflow_ref": f"{REPOSITORY}/.github/workflows/dadoku-build.yml@refs/heads/main",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "image": image,
        "platform": "linux/amd64",
        "verification": "workflow_output_not_independently_verified",
    }
    if document != expected or any(
        type(document.get(key)) is not int for key in ("version", "run_id", "run_attempt")
    ):
        raise ValueError("Evidence does not match the successful source run.")
    return image


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, timeout=120).strip()


def smoke(image, *, commit):
    docker("pull", "--platform", "linux/amd64", image)
    image_config = json.loads(docker("image", "inspect", image))[0]
    if (
        image_config["Os"] != "linux"
        or image_config["Architecture"] != "amd64"
        or image not in image_config["RepoDigests"]
        or image_config["Config"]["User"] != "10001:10001"
        or image_config["Config"]["Labels"]["org.opencontainers.image.revision"] != commit
        or image_config["Config"]["Labels"]["org.opencontainers.image.source"]
        != f"https://github.com/{REPOSITORY}"
    ):
        raise ValueError("Pulled image platform, digest, user or source labels do not match.")
    container = docker(
        "run",
        "--detach",
        "--platform",
        "linux/amd64",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--memory=128m",
        "--cpus=1",
        "--health-interval=2s",
        "--health-timeout=3s",
        "--health-start-period=2s",
        "--health-retries=3",
        "--publish",
        "127.0.0.1::8000",
        image,
    )
    if not re.fullmatch(r"[0-9a-f]{64}", container):
        raise ValueError("Docker did not return an exact container ID.")
    try:
        deadline = time.monotonic() + 60
        while True:
            state = json.loads(docker("inspect", container))[0]["State"]
            if not state["Running"]:
                raise RuntimeError(f"Container exited before health succeeded: {state}.")
            health = state["Health"]["Status"]
            if health == "healthy":
                break
            if health == "unhealthy" or time.monotonic() >= deadline:
                raise RuntimeError(f"Container failed health checks: {state}.")
            time.sleep(1)
        binding = docker("port", container, "8000/tcp")
        if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", binding):
            raise ValueError("Container port is not restricted to loopback.")
        origin = f"http://{binding}"
        for path, expected in (
            ("/healthz", {"status": "ok"}),
            (
                "/",
                {
                    "application": "dadoku-test-app",
                    "message": "Hello from Dadoku.",
                    "version": "1",
                },
            ),
        ):
            with urllib.request.urlopen(origin + path, timeout=5) as response:
                if response.status != 200 or json.load(response) != expected:
                    raise ValueError(f"Unexpected response from {path}.")
        with urllib.request.urlopen(
            urllib.request.Request(origin + "/", method="HEAD"), timeout=5
        ) as response:
            if response.status != 200 or response.read() != b"":
                raise ValueError("HEAD did not return a successful empty body.")
        try:
            urllib.request.urlopen(origin + "/missing", timeout=5)
        except HTTPError as error:
            with error:
                if error.code != 404 or json.load(error) != {"error": "not_found"}:
                    raise ValueError(
                        "Unknown path did not return the expected JSON 404."
                    ) from error
        else:
            raise ValueError("Unknown path unexpectedly succeeded.")
        docker("stop", "--time", "5", container)
        state = json.loads(docker("inspect", container))[0]["State"]
        if state["Running"] or state["ExitCode"] != 0 or state["OOMKilled"]:
            raise RuntimeError(f"SIGTERM did not stop the app cleanly: {state}.")
    finally:
        try:
            subprocess.run(["docker", "logs", container], check=True, timeout=15)
        finally:
            docker("rm", "--force", container)


def main():
    commit = os.environ["SOURCE_COMMIT"]
    run_id = int(os.environ["SOURCE_RUN_ID"])
    run_attempt = int(os.environ["SOURCE_RUN_ATTEMPT"])
    document = json.loads(Path(sys.argv[1]).read_text())
    image = validate_evidence(document, commit=commit, run_id=run_id, run_attempt=run_attempt)
    smoke(image, commit=commit)
    summary = (
        f"Container smoke acceptance passed for `{image}` at `{commit}`.\n\n"
        "Exact source-run evidence, platform, source labels and non-root user checked; "
        "read-only constrained container became healthy, served expected HTTP responses, "
        "and exited cleanly on SIGTERM. Test container removed.\n\n"
        "This is fixture acceptance, not independently verified provenance "
        "or deployment approval.\n"
    )
    print(summary)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
        output.write(summary)


if __name__ == "__main__":
    main()
