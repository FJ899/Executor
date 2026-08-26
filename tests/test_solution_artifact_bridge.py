from __future__ import annotations

import copy
import unittest

from executor.solution_artifact import runtime_solution_proposal
from executor.solution_proposal import SolutionProposalError, validate_solution_proposal
from tests.test_solution_proposal import frozen_result, proposal


class SolutionArtifactBridgeTests(unittest.TestCase):
    def test_validated_provider_artifact_round_trips_into_runtime_shape(self) -> None:
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        raw = proposal(frozen)
        validated = validate_solution_proposal(raw, frozen_result=frozen)
        artifact = validated.to_dict()

        self.assertNotIn("schema_version", artifact)
        self.assertIn("payload_sha256", artifact)
        runtime = runtime_solution_proposal(artifact, frozen_result=frozen)

        self.assertEqual(runtime, raw)
        revalidated = validate_solution_proposal(runtime, frozen_result=frozen)
        self.assertEqual(revalidated.payload_sha256, artifact["payload_sha256"])
        self.assertEqual(
            revalidated.provenance_sha256,
            artifact["provenance_sha256"],
        )

    def test_tampered_validated_artifact_hashes_fail_closed(self) -> None:
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        artifact = validate_solution_proposal(
            proposal(frozen), frozen_result=frozen
        ).to_dict()

        for field in ("payload_sha256", "provenance_sha256"):
            with self.subTest(field=field):
                tampered = copy.deepcopy(artifact)
                tampered[field] = "0" * 64
                with self.assertRaises(SolutionProposalError):
                    runtime_solution_proposal(tampered, frozen_result=frozen)

    def test_raw_runtime_proposal_remains_supported(self) -> None:
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        raw = proposal(frozen)
        self.assertEqual(
            runtime_solution_proposal(raw, frozen_result=frozen),
            raw,
        )


if __name__ == "__main__":
    unittest.main()
