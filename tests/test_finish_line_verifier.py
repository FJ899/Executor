from __future__ import annotations

import importlib.util
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "finish_line_verifier" / "verify.py"
spec = importlib.util.spec_from_file_location("finish_line_verifier", VERIFIER)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class FinishLineVerifierTests(unittest.TestCase):
    def test_candidate_declared_pass_is_non_authoritative(self):
        self.assertEqual(
            module.CANDIDATE_DECLARED_VERDICT_AUTHORITY,
            "IGNORED_FOR_AUTHORITY",
        )

    def test_strict_json_rejects_duplicate_keys(self):
        with self.assertRaises(module.VerificationError):
            module.strict_json(b'{"status":"PASS","status":"FAIL"}', label="duplicate")

    def test_zip_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.json", "{}")
            with self.assertRaises(module.VerificationError):
                module.EvidenceZip(path)

    def test_zip_rejects_symlink_member(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(info, "target")
            with self.assertRaises(module.VerificationError):
                module.EvidenceZip(path)

    def test_canonical_json_hash_is_order_independent(self):
        left = module.canonical_json_bytes({"b": 2, "a": 1})
        right = module.canonical_json_bytes(json.loads('{"a":1,"b":2}'))
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
