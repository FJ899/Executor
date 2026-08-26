from __future__ import annotations

import dataclasses
import json
import unittest

from executor.product_cli import _json_default


@dataclasses.dataclass(frozen=True)
class _VerifiedLeaf:
    object_id: str
    _proof: object = dataclasses.field(default_factory=object, repr=False, compare=False)


@dataclasses.dataclass(frozen=True)
class _VerifiedEnvelope:
    status: str
    leaf: _VerifiedLeaf
    _proof: object = dataclasses.field(default_factory=object, repr=False, compare=False)


class ProductCliSerializationTests(unittest.TestCase):
    def test_private_verification_sentinels_are_not_serialized(self) -> None:
        value = _VerifiedEnvelope(
            status="EFFECT_COMPLETED_AND_OBSERVED",
            leaf=_VerifiedLeaf(object_id="94"),
        )

        encoded = json.dumps({"result": value}, default=_json_default)
        decoded = json.loads(encoded)

        self.assertEqual(
            decoded,
            {
                "result": {
                    "status": "EFFECT_COMPLETED_AND_OBSERVED",
                    "leaf": {"object_id": "94"},
                }
            },
        )
        self.assertNotIn("_proof", encoded)


if __name__ == "__main__":
    unittest.main()
