import os
import tempfile
import unittest
from pathlib import Path

from executor.repository_access import RepositoryPathError, resolve_repository_file


class VerifiedPathReadTest(unittest.TestCase):
    def test_link_count_is_rechecked_when_resolved_path_is_read_later(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "source.txt"
            source.write_text("evidence\n", encoding="utf-8")
            _, resolved = resolve_repository_file(root, "source.txt")
            os.link(source, root / "late-hardlink.txt")
            with self.assertRaisesRegex(RepositoryPathError, "link count"):
                resolved.read_text(encoding="utf-8")

    def test_regular_resolved_path_uses_verified_read(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "source.txt"
            source.write_text("evidence\n", encoding="utf-8")
            _, resolved = resolve_repository_file(root, "source.txt")
            self.assertEqual(resolved.read_text(encoding="utf-8"), "evidence\n")


if __name__ == "__main__":
    unittest.main()
