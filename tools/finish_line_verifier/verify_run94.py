#!/usr/bin/env python3
"""Read-only extension of the accepted finish-line verifier for P4 run 94."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ACCEPTED = HERE / "verify.py"
spec = importlib.util.spec_from_file_location("accepted_finish_line_verifier", ACCEPTED)
base = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(base)

AUTH = "IGNORED_FOR_AUTHORITY"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise base.VerificationError(message)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_value(path: Path, label: str) -> Any:
    def reject(value: str) -> None:
        raise base.VerificationError(f"non-standard JSON constant in {label}: {value}")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=base._pairs, parse_constant=reject)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise base.VerificationError(f"invalid {label}: {exc}") from exc


def when(value: Any, label: str) -> dt.datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"invalid {label}")
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise base.VerificationError(f"invalid {label}") from exc


def fresh(receipt: dict[str, Any], label: str) -> None:
    require(receipt.get("state") == "FINAL" and receipt.get("terminal_success") is True, f"{label} not FINAL success")
    require(when(receipt.get("provider_created_at"), label) < when(receipt.get("not_after"), label), f"{label} not fresh")


def provider_bindings(args: argparse.Namespace, common: dict[str, Any]) -> None:
    run = json_value(args.run_metadata, "run metadata")
    require(isinstance(run, dict), "run metadata must be object")
    require(str(run.get("id")) == common["run_id"], "run id mismatch")
    require(run.get("head_sha") == common["executor_head"] and run.get("head_branch") == common["head_branch"], "run head/ref mismatch")
    require(run.get("path") == common["workflow_path"] and run.get("event") == "workflow_dispatch", "run workflow/trigger mismatch")
    require(run.get("status") == "completed" and run.get("conclusion") == "success" and int(run.get("run_attempt", -1)) == common["run_attempt"], "run status/attempt mismatch")

    meta = json_value(args.artifacts_metadata, "artifact metadata")
    require(isinstance(meta, dict) and isinstance(meta.get("artifacts"), list), "artifact metadata invalid")
    by_id = {x.get("id"): x for x in meta["artifacts"] if isinstance(x, dict)}
    for name, exp in common["artifacts"].items():
        item = by_id.get(exp["artifact_id"])
        require(isinstance(item, dict), f"{name} provider artifact missing")
        require(item.get("name") == exp["artifact_name"] and item.get("digest") == f"sha256:{exp['artifact_sha256']}" and item.get("expired") is False, f"{name} provider artifact mismatch")
        wr = item.get("workflow_run", {})
        require(str(wr.get("id")) == common["run_id"] and wr.get("head_sha") == common["executor_head"], f"{name} provider run binding mismatch")


def extra_artifact_checks(name: str, path: Path, common: dict[str, Any], exp: dict[str, Any]) -> None:
    z = base.EvidenceZip(path)
    try:
        for i, run_id in enumerate(exp["run_ids"], 1):
            frozen = z.json(f"{name}-frozen-{i}.json")
            proposal = z.json(f"{name}-proposal-{i}.json")
            result = z.json(f"{name}-result-{i}.json")
            decision = frozen.get("contract", {}).get("decision_evidence", {})
            expected = exp["decisions"][i - 1]
            actor = decision.get("actor", {})
            require((decision.get("comment_id"), decision.get("comment_node_id"), decision.get("body_sha256")) == (expected["comment_id"], expected["comment_node_id"], expected["body_sha256"]), f"{name} decision binding {i} mismatch")
            require((actor.get("login"), actor.get("id")) == (exp["human_actor_login"], exp["human_actor_id"]), f"{name} human actor {i} mismatch")
            require(frozen.get("authority_snapshot_sha256") == exp["authority_snapshot_sha256s"][i - 1], f"{name} snapshot {i} mismatch")

            contract = frozen.get("decision_consumption", {}).get("global", {})
            require(contract.get("final_sha") == exp["contract_final_shas"][i - 1], f"{name} contract final sha {i} mismatch")
            fresh(contract, f"{name} contract {i}")
            effect = result.get("authority_consumption", {}).get("global", {})
            require(effect.get("final_sha") == exp["effect_final_shas"][i - 1], f"{name} effect final sha {i} mismatch")
            fresh(effect, f"{name} effect {i}")

            prov = proposal.get("provenance", {})
            require((prov.get("provider"), prov.get("model"), prov.get("prompt_sha256")) == (exp["model_provider"], exp["model"], exp["prompt_sha256"]), f"{name} model provenance {i} mismatch")
            muts = proposal.get("mutations")
            require(isinstance(muts, list) and len(muts) == 1 and muts[0].get("path") == exp["changed_path"], f"{name} mutation {i} mismatch")
            text = muts[0].get("replacement_text")
            require(isinstance(text, str) and hashlib.sha256(text.encode()).hexdigest() == exp["reviewed_file_sha256"], f"{name} reviewed output {i} mismatch")
            require(result.get("run_id") == run_id, f"{name} run id {i} mismatch")
    finally:
        z.close()


def review_binding(path: Path, file_path: Path, exp: dict[str, Any], coverage: int) -> dict[str, Any]:
    reviews = json_value(path, "pull request reviews")
    require(isinstance(reviews, list), "reviews must be array")
    matches = [x for x in reviews if isinstance(x, dict) and x.get("id") == exp["review_id"] and x.get("state") == "APPROVED" and x.get("commit_id") == exp["reviewed_head"] and isinstance(x.get("user"), dict) and x["user"].get("login") == exp["reviewer_login"]]
    require(len(matches) == 1, "approved review binding missing or ambiguous")
    require(sha_file(file_path) == exp["reviewed_file_sha256"], "reviewed file hash mismatch")
    return {"repository": exp["repository"], "pr_number": exp["pr_number"], "review_id": exp["review_id"], "reviewed_head": exp["reviewed_head"], "coverage": coverage}


def change_stability(old: Path, new: Path, exp: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    a, b = old.read_text(encoding="utf-8"), new.read_text(encoding="utf-8")
    require(sha_file(old) == exp["baseline_workflow_sha256"] and sha_file(new) == exp["current_workflow_sha256"], "workflow hash mismatch")
    require(a.count(exp["old_dependency"]) == 1 and b.count(exp["new_dependency"]) == 1, "dependency occurrence mismatch")
    require(a.count(exp["historical_ref"]) == 2 and b.count(exp["dedicated_ref"]) == 2, "ref occurrence mismatch")
    require(b.replace(exp["new_dependency"], exp["old_dependency"]).replace(exp["dedicated_ref"], exp["historical_ref"]) == a, "workflow delta exceeds dependency/ref binding")
    require(exp["old_image_id"] != exp["new_image_id"], "resolved image identity did not change")
    require(artifacts["scriptops"]["patch_sha256"] == exp["historical_scriptops_patch_sha256"], "ScriptOps patch changed after dependency change")
    require(artifacts["reconstructor"]["patch_sha256"] == exp["historical_reconstructor_patch_sha256"], "Reconstructor patch changed after dependency change")
    return {"status": "PASS", "dependency_change": f"{exp['old_dependency']} -> {exp['new_dependency']}", "old_image_id": exp["old_image_id"], "new_image_id": exp["new_image_id"], "task_semantics_change": False, "capability_change": False}


def verify(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    common = manifest["p4_run94"]
    provider_bindings(args, common)
    artifacts = {}
    for name, path in (("scriptops", args.scriptops), ("reconstructor", args.reconstructor)):
        exp = common["artifacts"][name]
        artifacts[name] = base.verify_p4_artifact(name, path, common, exp)
        extra_artifact_checks(name, path, common, exp)
    require(sum(len(x["runs"]) for x in artifacts.values()) == common["expected_execution_count"] == 6 and len(artifacts) == common["expected_objective_count"] == 2, "objective/execution count mismatch")

    reviews = {
        "scriptops": review_binding(args.scriptops_reviews, args.scriptops_reviewed_file, common["artifacts"]["scriptops"]["review"], 3),
        "reconstructor": review_binding(args.reconstructor_reviews, args.reconstructor_reviewed_file, common["artifacts"]["reconstructor"]["review"], 3),
    }
    require(sum(x["coverage"] for x in reviews.values()) == 6, "review coverage is not 6/6")
    stability = change_stability(args.baseline_workflow, args.current_workflow, common["change_stability"], artifacts)
    return {
        "scope": "P4_RUN_94_FRESH_CHANGE_STABILITY_REPROOF",
        "raw_evidence_status": "PASS",
        "g13_replay_input_status": "PASS",
        "g15_inputs_status": "PASS",
        "executor_head": common["executor_head"], "executor_tree": common["executor_tree"], "workflow_run_id": common["run_id"],
        "objectives": 2, "executions": 6, "successful_review_required_results": 6, "reviewed_output_coverage": "6/6", "human_provider_review_events": 2,
        "artifacts": artifacts, "review_bindings": reviews, "change_stability": stability,
        "model_identity": {"provider": common["model_provider"], "model": common["model"]},
        "candidate_generated_verdict_authority": AUTH,
        "p4_completion_status": "NOT_DECIDED_BY_THIS_VERIFIER",
        "not_established_by_this_verifier": ["G02_CANONICAL_CLAIM_RECONCILIATION", "G16_REPOSITORY_CLOSURE", "G17_TRUST_ROOT_ACCEPTANCE_AND_INDEPENDENT_COMPLETION_VERDICT", "G18_FINAL_HUMAN_EXECUTOR_1_0_ACCEPTANCE", "RELEASE_DEPLOY_TAG_AUTHORITY"],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    for name in ("manifest", "scriptops", "reconstructor", "run_metadata", "artifacts_metadata", "scriptops_reviews", "scriptops_reviewed_file", "reconstructor_reviews", "reconstructor_reviewed_file", "baseline_workflow", "current_workflow"):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    manifest = base.strict_json(args.manifest.read_bytes(), str(args.manifest))
    require(manifest.get("candidate_declared_verdict_authority") == AUTH, "manifest authority rule mismatch")
    try:
        result = verify(args, manifest)
    except base.VerificationError as exc:
        result = {"scope": "P4_RUN_94_FRESH_CHANGE_STABILITY_REPROOF", "status": "FAIL", "error": str(exc), "candidate_generated_verdict_authority": AUTH}
        code = 1
    else:
        code = 0
    payload = {"schema_version": "executor-finish-line-verifier-run94-result/1.0", **result, "verifier_identity": {"extension_code_sha256": sha_file(Path(__file__).resolve()), "accepted_verifier_git_blob": manifest["extends_accepted_trust_root"]["verify_git_blob"], "manifest_sha256": sha_file(args.manifest), "candidate_code_imported": False, "authoritative_use_requires": "SEPARATELY_ACCEPTED_TRUST_ROOT"}}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(text, end="") if args.output is None else args.output.write_text(text, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
