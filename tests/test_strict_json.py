import tempfile
import unittest
from pathlib import Path

from executor.strict_json import StrictJsonError, load_json_object, loads_json_object


class StrictJsonTest(unittest.TestCase):
    def test_duplicate_keys_are_rejected(self):
        with self.assertRaisesRegex(StrictJsonError, "Duplicate JSON object key"):
            loads_json_object('{"execution":{"default_network":false,"default_network":true}}')

    def test_nonstandard_constants_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaisesRegex(StrictJsonError, "Non-standard JSON constant"):
                loads_json_object(f'{{"value":{value}}}')

    def test_document_must_be_object(self):
        with self.assertRaisesRegex(StrictJsonError, "must contain an object"):
            loads_json_object('[1, 2, 3]')

    def test_file_loader_uses_same_rules(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "contract.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaises(StrictJsonError):
                load_json_object(path)


if __name__ == "__main__":
    unittest.main()
