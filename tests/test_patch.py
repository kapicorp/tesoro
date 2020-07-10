import unittest
from tesoro.patch import redact_patch

class TestPatch(unittest.TestCase):
    def test_redact_patch(self):
        patch = [
            {"op": "add", "path": "/a/b", "value": "secret value to redact"},
            {"op": "add", "path": "/metadata/annotations/tesoro.kapicorp.com~1revealed", "value": "no redact"}
        ]
        redacted = redact_patch(patch)

        self.assertEqual(patch[0]["value"], "secret value to redact")
        self.assertEqual(redacted[0]["value"], "!REDACTED VALUE!")
        self.assertEqual(redacted[1]["value"], "no redact")
