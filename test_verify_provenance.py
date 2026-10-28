import json
import subprocess
import unittest
from unittest.mock import patch

from ci_smoke import REPOSITORY
from verify_provenance import verified_subject, verify, verify_command


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.image = f"ghcr.io/{REPOSITORY}@sha256:" + "c" * 64
        self.results = [
            {
                "verificationResult": {
                    "statement": {
                        "predicateType": "https://slsa.dev/provenance/v1",
                        "subject": [
                            {"name": f"ghcr.io/{REPOSITORY}", "digest": {"sha256": "c" * 64}}
                        ],
                    }
                },
            }
        ]

    def test_exact_verifier_policy(self):
        command = verify_command(self.image, commit="a" * 40)
        for flag, value in (
            ("--repo", REPOSITORY),
            ("--source-digest", "a" * 40),
            ("--signer-digest", "a" * 40),
            ("--source-ref", "refs/heads/main"),
            ("--signer-workflow", REPOSITORY + "/.github/workflows/dadoku-build.yml"),
        ):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--deny-self-hosted-runners", command)
        self.assertIn("oci://" + self.image, command)

    def test_exact_subject_and_predicate_required(self):
        verified_subject(self.results, self.image)
        for result in ([], {}, [{"verificationResult": {}}]):
            with self.subTest(result=result), self.assertRaises(ValueError):
                verified_subject(result, self.image)
        with self.assertRaises(ValueError):
            verified_subject(self.results, "ghcr.io/other/repo@sha256:" + "c" * 64)
        with self.assertRaises(ValueError):
            verified_subject(self.results, f"ghcr.io/{REPOSITORY}@sha256:" + "d" * 64)

    @patch("verify_provenance.subprocess.run")
    def test_positive_and_negative_policy_checks(self, run):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=json.dumps(self.results), stderr=""),
            subprocess.CompletedProcess([], 1, stdout="", stderr="policy mismatch"),
            subprocess.CompletedProcess([], 1, stdout="", stderr="policy mismatch"),
        ]
        self.assertEqual(verify(self.image, commit="a" * 40), self.results)
        self.assertEqual(run.call_count, 3)

    @patch("verify_provenance.subprocess.run")
    def test_verifier_failure_and_unexpected_negative_success_are_not_ignored(self, run):
        run.side_effect = subprocess.CalledProcessError(1, ["gh"])
        with self.assertRaises(subprocess.CalledProcessError):
            verify(self.image, commit="a" * 40)
        run.side_effect = None
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(self.results), stderr=""
        )
        with self.assertRaisesRegex(ValueError, "unexpectedly accepted"):
            verify(self.image, commit="a" * 40)


if __name__ == "__main__":
    unittest.main()
