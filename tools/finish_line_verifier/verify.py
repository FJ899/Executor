#!/usr/bin/env python3
"""Read-only verifier for exact historical finish-line artifacts.

Stdlib only. Candidate code is never imported and candidate-generated PASS markers
are observations only. Authoritative use requires this code + manifest to execute
from a separately accepted trust-root identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

CANDIDATE_DECLARED_VERDICT_AUTHORITY = "IGNORED_FOR_AUTHORITY"


class VerificationError(RuntimeError):
    pass


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in items:
        if key in out:
            raise VerificationError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def strict_json(data: bytes, label: str = "JSON") -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise VerificationError(f"non-standard JSON constant in {label}: {value}")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must be an object")
    return value


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise VerificationError(message)


class EvidenceZip:
    def __init__(self, path: Path):
        self.z = zipfile.ZipFile(path)
        infos = self.z.infolist()
        names = [item.filename for item in infos]
        require(len(names) == len(set(names)), "duplicate ZIP member")
        for item in infos:
            part = PurePosixPath(item.filename)
            mode = (item.external_attr >> 16) & 0xFFFF
            require(not part.is_absolute() and ".." not in part.parts and "\\" not in item.filename, f"unsafe ZIP path: {item.filename}")
            require(not stat.S_ISLNK(mode), f"symlink ZIP member: {item.filename}")
        self.names = tuple(names)

    def close(self) -> None:
        self.z.close()

    def read(self, name: str) -> bytes:
        require(name in self.names, f"missing ZIP member: {name}")
        return self.z.read(name)

    def text(self, name: str) -> str:
        try:
            return self.read(name).decode()
        except UnicodeError as exc:
            raise VerificationError(f"non-UTF-8 member: {name}") from exc

    def json(self, name: str) -> dict[str, Any]:
        return strict_json(self.read(name), name)


def ledger_rows(z: EvidenceZip, member: str) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        db.write_bytes(z.read(member))
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT authority_key,action_kind,run_id,state,result_sha256,result_json FROM authority_consumptions ORDER BY consumed_at").fetchall()
        except sqlite3.Error as exc:
            raise VerificationError(f"cannot inspect {member}: {exc}") from exc
        finally:
            if "con" in locals():
                con.close()
    out = []
    for row in rows:
        item = dict(row)
        raw = item.pop("result_json")
        require(item["state"] == "FINAL" and isinstance(raw, bytes), f"non-final ledger row: {item['authority_key']}")
        require(sha(raw) == item["result_sha256"], f"ledger result hash mismatch: {item['authority_key']}")
        strict_json(raw, f"ledger:{item['authority_key']}")
        out.append(item)
    return out


def verify_m05(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    exp = manifest["m05"]
    artifact_sha = file_sha(path)
    require(artifact_sha == exp["artifact_sha256"], "M05 artifact hash mismatch")
    z = EvidenceZip(path)
    try:
        require(sorted(z.names) == sorted(exp["expected_members"]), "M05 member set mismatch")
        require(z.text("m05-r1-executor-head.txt").strip() == exp["executor_head"], "M05 executor head mismatch")
        require(z.text("m05-r1-executor-tree.txt").strip() == exp["executor_tree"], "M05 executor tree mismatch")
        require(z.text("m05-r1-workflow-sha256.txt").split()[0] == exp["workflow_sha256"], "M05 workflow mismatch")
        gate, frozen, proposal, result = (z.json(name) for name in ("m05-r1-provider-gate.json", "m05-r1-frozen.json", "m05-r1-proposal.json", "m05-r1-result.json"))
        require(result == z.json("m05-r1-runs/m05-r1-request65-32280682838-1/report.json"), "M05 report copies differ")
        require(gate.get("provider_verified") is True and gate.get("contract_authority_consumed") is True, "M05 provider/contract gate failed")
        require(gate.get("issue_number") == exp["request_issue"] and gate.get("comment_id") == exp["decision_comment_id"], "M05 Human request/decision mismatch")
        require(frozen.get("status") == "AUTHORIZED_AND_FROZEN" and frozen.get("contract_sha256") == exp["contract_sha256"], "M05 frozen contract mismatch")
        target = frozen.get("contract", {}).get("target", {})
        require((target.get("repository"), target.get("commit"), target.get("tree")) == (exp["target_repository"], exp["target_commit"], exp["target_tree"]), "M05 target mismatch")
        contract_global = frozen.get("decision_consumption", {}).get("global", {})
        require(contract_global.get("state") == "FINAL" and contract_global.get("final_sha") == exp["contract_authority_final_sha"], "M05 contract receipt mismatch")
        provenance = proposal.get("provenance", {})
        require(provenance.get("producer_role") == "EXTERNAL_INTELLIGENCE" and provenance.get("human_solution_edits") == 0 and provenance.get("effect_capability") == "NONE", "M05 proposal provenance mismatch")
        require(result.get("status") == "ACTION_COMPLETED_REVIEW_REQUIRED" and result.get("human_review_required") is True and result.get("merge_allowed") is False, "M05 terminal status mismatch")
        require(result.get("changed_paths") == exp["expected_changed_paths"], "M05 changed paths mismatch")
        env = result.get("execution_environment", {})
        require((str(env.get("workflow_run_id")), env.get("executor_commit"), env.get("workflow_sha256"), env.get("sandbox_image_id")) == (exp["run_id"], exp["executor_head"], exp["workflow_sha256"], exp["sandbox_image_id"]), "M05 environment mismatch")
        patch = z.read("m05-r1-target.patch")
        require(patch == z.read("m05-r1-runs/m05-r1-request65-32280682838-1/change.patch") and sha(patch) == exp["patch_sha256"], "M05 patch mismatch")
        terminal = result.get("terminal_result")
        require(isinstance(terminal, dict), "M05 terminal result missing")
        result_sha = sha(canonical_json_bytes(terminal))
        require(result_sha == exp["result_sha256"], "M05 terminal result hash mismatch")
        effect = result.get("authority_consumption", {})
        require(effect.get("state") == "FINAL" and effect.get("result_sha256") == result_sha, "M05 local effect binding mismatch")
        require(effect.get("global", {}).get("state") == "FINAL" and effect.get("global", {}).get("final_sha") == exp["effect_authority_final_sha"] and effect.get("global", {}).get("result_sha256") == result_sha, "M05 global effect binding mismatch")
        rows = ledger_rows(z, ".executor/m05-r1-authority.sqlite3")
        require(len(rows) == 2 and {row["action_kind"] for row in rows} == {"CONTRACT_ACCEPT", "EXTERNAL_PROJECT_EXECUTION"}, "M05 ledger shape mismatch")
        require(next(row for row in rows if row["action_kind"] == "EXTERNAL_PROJECT_EXECUTION")["result_sha256"] == result_sha, "M05 SQLite effect mismatch")
        candidate = z.read("m05-r1-verifier.json")
        return {"scope": "M05_R1_RAW_EXECUTION_EVIDENCE", "status": "PASS", "artifact_sha256": artifact_sha, "executor_head": exp["executor_head"], "target_commit": exp["target_commit"], "patch_sha256": exp["patch_sha256"], "result_sha256": result_sha, "candidate_generated_verifier": {"sha256": sha(candidate), "authority": CANDIDATE_DECLARED_VERDICT_AUTHORITY, "status_field_used_for_verdict": False}}
    finally:
        z.close()


def verify_p4_artifact(name: str, path: Path, common: dict[str, Any], exp: dict[str, Any]) -> dict[str, Any]:
    artifact_sha = file_sha(path)
    require(artifact_sha == exp["artifact_sha256"], f"P4 {name} artifact hash mismatch")
    z = EvidenceZip(path)
    try:
        require(z.text(f"{name}-executor-head.txt").strip() == common["executor_head"] and z.text(f"{name}-executor-tree.txt").strip() == common["executor_tree"], f"P4 {name} executor identity mismatch")
        require(z.text(f"{name}-workflow-sha256.txt").split()[0] == common["workflow_sha256"] and z.text(f"{name}-image-id.txt").strip() == exp["image_id"], f"P4 {name} environment identity mismatch")
        patches, effect_hashes, contract_hashes, effect_keys, contract_keys = [], set(), set(), set(), set()
        for index, run_id in enumerate(exp["run_ids"], 1):
            frozen, proposal, result = (z.json(f"{name}-{kind}-{index}.json") for kind in ("frozen", "proposal", "result"))
            require(result == z.json(f"pilot-evidence/{name}/runs/{run_id}/report.json"), f"P4 {name} report copy mismatch")
            require(frozen.get("status") == "AUTHORIZED_AND_FROZEN", f"P4 {name} contract not frozen")
            require((result.get("run_id"), result.get("repository"), result.get("source_commit"), result.get("source_tree")) == (run_id, exp["repository"], exp["source_commit"], exp["source_tree"]), f"P4 {name} run identity mismatch")
            require(result.get("status") == "ACTION_COMPLETED_REVIEW_REQUIRED" and result.get("human_review_required") is True and result.get("merge_allowed") is False and result.get("changed_paths") == [exp["changed_path"]], f"P4 {name} terminal/scope mismatch")
            env = result.get("execution_environment", {})
            require((str(env.get("workflow_run_id")), env.get("executor_commit"), env.get("workflow_sha256"), env.get("sandbox_image_id")) == (common["run_id"], common["executor_head"], common["workflow_sha256"], exp["image_id"]), f"P4 {name} execution environment mismatch")
            prov = proposal.get("provenance", {})
            require(proposal.get("proposal_id") == exp["proposal_id"] and prov.get("producer_role") == "EXTERNAL_INTELLIGENCE" and prov.get("human_solution_edits") == 0 and prov.get("effect_capability") == "NONE", f"P4 {name} proposal provenance mismatch")
            patch = z.read(f"{name}-pilot-{index}.patch")
            require(patch == z.read(f"pilot-evidence/{name}/runs/{run_id}/change.patch"), f"P4 {name} patch copy mismatch")
            patch_sha = sha(patch); patches.append(patch_sha)
            require(result.get("patch", {}).get("sha256") == patch_sha, f"P4 {name} patch hash mismatch")
            terminal = result.get("terminal_result"); require(isinstance(terminal, dict), f"P4 {name} terminal missing")
            terminal_sha = sha(canonical_json_bytes(terminal)); effect = result.get("authority_consumption", {}); global_effect = effect.get("global", {})
            require(effect.get("state") == "FINAL" and effect.get("result_sha256") == terminal_sha and global_effect.get("state") == "FINAL" and global_effect.get("result_sha256") == terminal_sha, f"P4 {name} effect binding mismatch")
            effect_hashes.add(terminal_sha); effect_keys.add(global_effect.get("authority_key"))
            contract = frozen.get("decision_consumption", {}).get("global", {})
            require(contract.get("state") == "FINAL", f"P4 {name} contract receipt mismatch")
            contract_hashes.add(contract.get("result_sha256")); contract_keys.add(contract.get("authority_key"))
        require(len(set(patches)) == 1 and len(effect_keys) == len(contract_keys) == len(effect_hashes) == len(contract_hashes) == 3, f"P4 {name} repeatability/authority uniqueness mismatch")
        dbs = [member for member in z.names if member.startswith(".executor/") and member.endswith("authority.sqlite3")]
        require(len(dbs) == 1, f"P4 {name} ledger count mismatch")
        rows = ledger_rows(z, dbs[0]); require(len(rows) == 6, f"P4 {name} ledger row count mismatch")
        require({row["result_sha256"] for row in rows if row["action_kind"] == "EXTERNAL_PROJECT_EXECUTION"} == effect_hashes and {row["result_sha256"] for row in rows if row["action_kind"] == "CONTRACT_ACCEPT"} == contract_hashes, f"P4 {name} ledger/result mismatch")
        return {"artifact_sha256": artifact_sha, "repository": exp["repository"], "runs": exp["run_ids"], "patch_sha256": patches[0], "contract_authority_count": 3, "effect_authority_count": 3, "terminal_status": "ACTION_COMPLETED_REVIEW_REQUIRED"}
    finally:
        z.close()


def verify_p4(scriptops: Path, reconstructor: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    common = manifest["p4"]
    return {"scope": "P4_RUN_91_RAW_EXECUTION_EVIDENCE", "raw_evidence_status": "PASS", "executor_head": common["executor_head"], "workflow_run_id": common["run_id"], "artifacts": {"scriptops": verify_p4_artifact("scriptops", scriptops, common, common["artifacts"]["scriptops"]), "reconstructor": verify_p4_artifact("reconstructor", reconstructor, common, common["artifacts"]["reconstructor"])}, "candidate_generated_verdict_authority": CANDIDATE_DECLARED_VERDICT_AUTHORITY, "p4_completion_status": "BLOCKED_ON_EXTERNAL_GATES", "not_established_by_this_verifier": ["ACTUAL_COST_MEASURED", "MODEL_OR_DEPENDENCY_CHANGE_STABILITY", "FINAL_HUMAN_ACCEPTANCE_AS_TECHNICAL_PROOF"]}


def write_result(path: Path | None, result: dict[str, Any], manifest_path: Path) -> None:
    payload = {"schema_version": "executor-finish-line-verifier-result/1.0", **result, "verifier_identity": {"code_sha256": file_sha(Path(__file__).resolve()), "manifest_sha256": file_sha(manifest_path), "candidate_code_imported": False, "authoritative_use_requires": "SEPARATELY_ACCEPTED_TRUST_ROOT"}}
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(text, end="") if path is None else path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--manifest", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    m05 = sub.add_parser("m05"); m05.add_argument("--artifact", type=Path, required=True); m05.add_argument("--output", type=Path)
    p4 = sub.add_parser("p4"); p4.add_argument("--scriptops", type=Path, required=True); p4.add_argument("--reconstructor", type=Path, required=True); p4.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    manifest = strict_json(args.manifest.read_bytes(), str(args.manifest)); require(manifest.get("candidate_declared_verdict_authority") == CANDIDATE_DECLARED_VERDICT_AUTHORITY, "manifest verdict-authority rule mismatch")
    try:
        result = verify_m05(args.artifact, manifest) if args.command == "m05" else verify_p4(args.scriptops, args.reconstructor, manifest)
    except VerificationError as exc:
        write_result(args.output, {"scope": args.command.upper(), "status": "FAIL", "error": str(exc), "candidate_generated_verdict_authority": CANDIDATE_DECLARED_VERDICT_AUTHORITY}, args.manifest); return 1
    write_result(args.output, result, args.manifest); return 0


if __name__ == "__main__":
    raise SystemExit(main())
