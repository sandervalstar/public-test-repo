import unittest

from ci_smoke import REPOSITORY, validate_evidence


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.expected = {"commit": "a" * 40, "run_id": 123, "run_attempt": 2}
        self.document = {
            "version": 1,
            "repository": REPOSITORY,
            "commit_sha": self.expected["commit"],
            "ref": "refs/heads/main",
            "workflow_ref": f"{REPOSITORY}/.github/workflows/dadoku-build.yml@refs/heads/main",
            "run_id": 123,
            "run_attempt": 2,
            "image": f"ghcr.io/{REPOSITORY}@sha256:" + "b" * 64,
            "platform": "linux/amd64",
            "verification": "workflow_output_not_independently_verified",
        }

    def test_exact_run_evidence(self):
        self.assertEqual(validate_evidence(self.document, **self.expected), self.document["image"])

    def test_missing_extra_or_changed_fields_are_rejected(self):
        for key in self.document:
            with self.subTest(key=key):
                missing = self.document.copy()
                missing.pop(key)
                for document in (missing, {**self.document, key: "unexpected"}):
                    with self.assertRaises(ValueError):
                        validate_evidence(document, **self.expected)
        with self.assertRaises(ValueError):
            validate_evidence({**self.document, "unexpected": True}, **self.expected)
        with self.assertRaises(ValueError):
            validate_evidence([], **self.expected)

    def test_boolean_identities_are_not_integers(self):
        for field in ("version", "run_id", "run_attempt"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_evidence({**self.document, field: True}, **self.expected)
        with self.assertRaises(ValueError):
            validate_evidence(self.document, **{**self.expected, "run_id": True})

    def test_mutable_foreign_or_invalid_images_are_rejected(self):
        for image in (
            f"ghcr.io/{REPOSITORY}:latest",
            "ghcr.io/another/repo@sha256:" + "b" * 64,
            self.document["image"] + "\n",
            f"ghcr.io/{REPOSITORY}@sha256:" + "z" * 64,
            None,
        ):
            with self.subTest(image=image), self.assertRaises(ValueError):
                validate_evidence({**self.document, "image": image}, **self.expected)


if __name__ == "__main__":
    unittest.main()
