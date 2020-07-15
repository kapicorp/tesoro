import unittest
from hashlib import sha256
from tesoro.patch import redact_patch


class TestPatch(unittest.TestCase):
    def test_redact_patch(self):
        patch = [
            {"op": "add", "path": "/a/b", "value": "secret value to redact"},
            {
                "op": "add",
                "path": "/metadata/annotations/tesoro.kapicorp.com~1revealed",
                "value": "no redact",
            },
        ]
        redacted = redact_patch(patch)

        self.assertEqual(patch[0]["value"], "secret value to redact")
        value_hash = sha256("secret value to redact".encode()).hexdigest()
        self.assertEqual(redacted[0]["value"], f"!REDACTED VALUE! sha256={value_hash}")
        self.assertEqual(redacted[1]["value"], "no redact")
