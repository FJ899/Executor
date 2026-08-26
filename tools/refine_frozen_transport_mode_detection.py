from pathlib import Path

path = Path("executor/frozen_pilot_authority.py")
text = path.read_text(encoding="utf-8")
old = '''    formation_transport_marked = any(
        (
            contract.get("schema_version") == "executor-frozen-pilot-contract/1.2",
            frozen_result.get("schema_version") == "executor-pilot-decision-result/1.2",
            contract_transport is not None,
            snapshot_transport is not None,
            result_transport is not None,
            isinstance(authority_boundary, dict)
            and (
                "request_transport_is_authority" in authority_boundary
                or "human_decision_is_authority" in authority_boundary
            ),
        )
    )
'''
new = '''    formation_transport_marked = any(
        (
            contract_transport is not None,
            snapshot_transport is not None,
            result_transport is not None,
            isinstance(authority_boundary, dict)
            and (
                "request_transport_is_authority" in authority_boundary
                or "human_decision_is_authority" in authority_boundary
            ),
        )
    )
'''
if text.count(old) != 1:
    raise SystemExit("expected broad formation transport detector not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
