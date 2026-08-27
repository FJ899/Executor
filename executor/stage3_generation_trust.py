from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executor.github_trust import canonical_json
from executor.stage3_evidence import read_canonical_json, sha256_bytes, sha256_json


class Stage3GenerationTrustError(ValueError):
    pass


_PROVIDER = "OpenAI"
_VERIFICATION_METHOD = "OPENAI_RESPONSES_RETRIEVE_V1"
_EVIDENCE_SCHEMA = "executor-provider-generation-evidence/1.0"
_REQUEST_SCHEMA = "executor-stage3-generation-verification-request/1.0"
_EVIDENCE_HASH_CONSTRUCTION = "SHA256_CANONICAL_JSON_WITHOUT_EVIDENCE_ARTIFACT_SHA256"
_POLICY_SCHEMA = "executor-stage3-generation-identity-policy/1.0"
_FIXED_GH = Path("/usr/bin/gh")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TRUST_ROOT = _REPOSITORY_ROOT / "trust_profiles" / "stage3_generation_attestation_root.jsonl"
_IDENTITY_POLICY = _REPOSITORY_ROOT / "trust_profiles" / "stage3_generation_identity_policy.json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Stage3GenerationTrustProfile:
    oidc_issuer: str
    repository: str
    signer_reusable_workflow: str
    signer_digest: str
    accepted_predicate_type: str
    accepted_evidence_schema: str
    verification_method: str
    trusted_root_sha256: str
    policy_sha256: str


@dataclass(frozen=True)
class TrustedProviderGenerationBinding:
    evidence: dict[str, Any]
    evidence_sha256: str
    attestation_bundle_sha256: str
    verification_request_sha256: str
    trust_profile: Stage3GenerationTrustProfile
    gh_verification_sha256: str

    @property
    def binding_sha256(self) -> str:
        return sha256_json({
            "schema_version": "executor-stage3-provider-generation-binding/1.0",
            "evidence_sha256": self.evidence_sha256,
            "attestation_bundle_sha256": self.attestation_bundle_sha256,
            "verification_request_sha256": self.verification_request_sha256,
            "trust_root_sha256": self.trust_profile.trusted_root_sha256,
            "identity_policy_sha256": self.trust_profile.policy_sha256,
            "gh_verification_sha256": self.gh_verification_sha256,
        })


def _require_sha(value: Any, *, label: str, git: bool = False) -> str:
    pattern = _GIT_SHA if git else _SHA256
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise Stage3GenerationTrustError(f"{label} is invalid")
    return value


def _load_profile() -> Stage3GenerationTrustProfile:
    try:
        root_bytes = _TRUST_ROOT.read_bytes()
        policy_bytes = _IDENTITY_POLICY.read_bytes()
    except OSError as exc:
        raise Stage3GenerationTrustError("runtime-installed Stage-3 trust profile is unavailable") from exc
    try:
        policy = json.loads(policy_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Stage3GenerationTrustError("runtime-installed Stage-3 identity policy is invalid") from exc
    if canonical_json(policy).encode("utf-8") != policy_bytes:
        raise Stage3GenerationTrustError("runtime-installed Stage-3 identity policy is not canonical JSON")
    expected = {"schema_version","oidc_issuer","repository","signer_reusable_workflow","signer_digest","accepted_predicate_type","accepted_evidence_schema","verification_method","trusted_root_sha256"}
    if not isinstance(policy, dict) or set(policy) != expected:
        raise Stage3GenerationTrustError("runtime-installed Stage-3 identity policy fields are invalid")
    exact = {
        "schema_version": _POLICY_SCHEMA,
        "oidc_issuer": "https://token.actions.githubusercontent.com",
        "repository": "FJ899/Executor",
        "signer_reusable_workflow": ".github/workflows/stage3-generation-verifier-attestation.yml",
        "accepted_evidence_schema": _EVIDENCE_SCHEMA,
        "verification_method": _VERIFICATION_METHOD,
    }
    for field, required in exact.items():
        if policy.get(field) != required:
            raise Stage3GenerationTrustError(f"runtime-installed Stage-3 identity policy {field} mismatch")
    _require_sha(policy.get("signer_digest"), label="signer digest", git=True)
    trusted_root_sha = sha256_bytes(root_bytes)
    if policy.get("trusted_root_sha256") != trusted_root_sha:
        raise Stage3GenerationTrustError("runtime-installed trusted-root content hash mismatch")
    lines = [line for line in root_bytes.splitlines() if line]
    if not lines:
        raise Stage3GenerationTrustError("runtime-installed trusted root is empty")
    try:
        roots = [json.loads(line.decode("utf-8")) for line in lines]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Stage3GenerationTrustError("runtime-installed trusted root is malformed JSONL") from exc
    if not all(isinstance(item, dict) and item.get("mediaType") == "application/vnd.dev.sigstore.trustedroot+json;version=0.1" for item in roots):
        raise Stage3GenerationTrustError("runtime-installed trusted root media type mismatch")
    return Stage3GenerationTrustProfile(
        oidc_issuer=policy["oidc_issuer"], repository=policy["repository"],
        signer_reusable_workflow=policy["signer_reusable_workflow"], signer_digest=policy["signer_digest"],
        accepted_predicate_type=policy["accepted_predicate_type"], accepted_evidence_schema=policy["accepted_evidence_schema"],
        verification_method=policy["verification_method"], trusted_root_sha256=trusted_root_sha,
        policy_sha256=sha256_bytes(policy_bytes),
    )


def runtime_trust_bundle_sha256() -> str:
    return _load_profile().trusted_root_sha256


def runtime_identity_policy_sha256() -> str:
    return _load_profile().policy_sha256


def _expected_request(*, frozen_result: dict[str, Any], stage2_result: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    provenance = proposal.get("provenance")
    contract = frozen_result.get("contract")
    if not isinstance(provenance, dict) or not isinstance(contract, dict):
        raise Stage3GenerationTrustError("frozen proposal/provenance input is incomplete")
    request_evidence = contract.get("request_evidence")
    if not isinstance(request_evidence, dict):
        raise Stage3GenerationTrustError("frozen request evidence is missing")
    consumption = frozen_result.get("decision_consumption")
    if not isinstance(consumption, dict) or consumption.get("state") != "FINAL" or consumption.get("terminal_success") is not True:
        raise Stage3GenerationTrustError("terminal Stage-2 freeze receipt is not successful")
    return {
        "schema_version": _REQUEST_SCHEMA,
        "provider": stage2_result.get("provider"), "model": stage2_result.get("model"),
        "generation_evidence_ref": stage2_result.get("generation_evidence_ref"),
        "provider_generation_timestamp": provenance.get("generated_at"),
        "frozen_task_contract_sha256": proposal.get("contract_sha256"), "repository": proposal.get("repository"),
        "source_commit": proposal.get("source_commit"), "source_tree": proposal.get("source_tree"),
        "source_context_sha256": stage2_result.get("context_sha256"), "prompt_sha256": stage2_result.get("prompt_sha256"),
        "response_sha256": stage2_result.get("generation_response_sha256"),
        "generation_challenge_sha256": stage2_result.get("generation_challenge_sha256"),
        "generation_challenge_issued_at": stage2_result.get("generation_challenge_issued_at"),
        "terminal_freeze_receipt_sha256": sha256_json(consumption),
        "request_binding": {
            "repository": request_evidence.get("repository"), "issue_number": request_evidence.get("issue_number"),
            "issue_node_id": request_evidence.get("issue_node_id"), "body_sha256": request_evidence.get("body_sha256"),
        },
        "proposal_payload_sha256": stage2_result.get("proposal_sha256"),
    }


def _validate_evidence_semantics(evidence: dict[str, Any], *, raw: bytes, profile: Stage3GenerationTrustProfile, frozen_result: dict[str, Any], stage2_result: dict[str, Any], proposal: dict[str, Any]) -> str:
    expected_keys = {"schema_version","provider","model","generation_evidence_ref","provider_record_id","provider_generation_timestamp","frozen_task_contract_sha256","repository","source_commit","source_tree","source_context_sha256","prompt_sha256","response_sha256","generation_challenge_sha256","generation_challenge_issued_at","terminal_freeze_receipt_sha256","proposal_payload_sha256","verification_method","verifier_repository","verifier_reusable_workflow_path","verifier_workflow_source_commit","verification_request_sha256","evidence_hash_construction","attestation_predicate_type","evidence_artifact_sha256"}
    if set(evidence) != expected_keys:
        raise Stage3GenerationTrustError("provider-generation evidence has invalid fields")
    if evidence.get("schema_version") != _EVIDENCE_SCHEMA:
        raise Stage3GenerationTrustError("provider-generation evidence schema mismatch")
    if evidence.get("provider") != _PROVIDER or evidence.get("verification_method") != _VERIFICATION_METHOD:
        raise Stage3GenerationTrustError("provider-generation evidence uses an untrusted provider profile")
    if evidence.get("provider_record_id") != evidence.get("generation_evidence_ref"):
        raise Stage3GenerationTrustError("provider-generation evidence record identity mismatch")
    exact = {
        "verifier_repository": profile.repository,
        "verifier_reusable_workflow_path": profile.signer_reusable_workflow,
        "verifier_workflow_source_commit": profile.signer_digest,
        "attestation_predicate_type": profile.accepted_predicate_type,
        "evidence_hash_construction": _EVIDENCE_HASH_CONSTRUCTION,
    }
    for field, required in exact.items():
        if evidence.get(field) != required:
            raise Stage3GenerationTrustError(f"provider-generation {field} mismatch")
    material = copy.deepcopy(evidence); claimed_self_hash = material.pop("evidence_artifact_sha256")
    if not isinstance(claimed_self_hash, str) or _SHA256.fullmatch(claimed_self_hash) is None or sha256_json(material) != claimed_self_hash:
        raise Stage3GenerationTrustError("provider-generation evidence canonical self hash mismatch")
    request = _expected_request(frozen_result=frozen_result, stage2_result=stage2_result, proposal=proposal)
    request_sha = sha256_json(request)
    if evidence.get("verification_request_sha256") != request_sha:
        raise Stage3GenerationTrustError("provider-generation verification request binding mismatch")
    pairs = (
        ("provider",request["provider"]),("model",request["model"]),("generation_evidence_ref",request["generation_evidence_ref"]),
        ("provider_generation_timestamp",request["provider_generation_timestamp"]),("frozen_task_contract_sha256",request["frozen_task_contract_sha256"]),
        ("repository",request["repository"]),("source_commit",request["source_commit"]),("source_tree",request["source_tree"]),
        ("source_context_sha256",request["source_context_sha256"]),("prompt_sha256",request["prompt_sha256"]),
        ("response_sha256",request["response_sha256"]),("generation_challenge_sha256",request["generation_challenge_sha256"]),
        ("generation_challenge_issued_at",request["generation_challenge_issued_at"]),("terminal_freeze_receipt_sha256",request["terminal_freeze_receipt_sha256"]),
        ("proposal_payload_sha256",request["proposal_payload_sha256"]),
    )
    for field, required in pairs:
        if evidence.get(field) != required:
            raise Stage3GenerationTrustError(f"provider-generation {field} mismatch")
    for field in ("frozen_task_contract_sha256","source_context_sha256","prompt_sha256","response_sha256","generation_challenge_sha256","terminal_freeze_receipt_sha256","proposal_payload_sha256","verification_request_sha256"):
        _require_sha(evidence.get(field), label=field)
    _require_sha(evidence.get("source_commit"), label="source commit", git=True)
    _require_sha(evidence.get("source_tree"), label="source tree", git=True)
    _require_sha(evidence.get("verifier_workflow_source_commit"), label="verifier workflow source", git=True)
    if canonical_json(evidence).encode("utf-8") != raw:
        raise Stage3GenerationTrustError("provider-generation evidence bytes are not canonical")
    return request_sha


def _verify_attestation_offline(*, evidence_path: Path, bundle_path: Path, evidence_sha256: str, profile: Stage3GenerationTrustProfile, expected_request_sha256: str) -> str:
    if not _FIXED_GH.is_file():
        raise Stage3GenerationTrustError("runtime-installed fixed GitHub attestation verifier is unavailable")
    argv = [str(_FIXED_GH),"attestation","verify",str(evidence_path),"--repo",profile.repository,"--bundle",str(bundle_path),"--custom-trusted-root",str(_TRUST_ROOT),"--cert-oidc-issuer",profile.oidc_issuer,"--signer-workflow",f"{profile.repository}/{profile.signer_reusable_workflow}","--signer-digest",profile.signer_digest,"--predicate-type",profile.accepted_predicate_type,"--deny-self-hosted-runners","--format","json"]
    try:
        completed = subprocess.run(argv, check=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={"HOME":"/nonexistent","PATH":"/usr/bin:/bin","GH_CONFIG_DIR":"/nonexistent","LC_ALL":"C.UTF-8"}, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Stage3GenerationTrustError("offline artifact-attestation verifier failed to execute") from exc
    if completed.returncode != 0:
        raise Stage3GenerationTrustError("offline artifact-attestation verification failed")
    try:
        results = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Stage3GenerationTrustError("offline attestation verifier returned invalid JSON") from exc
    if not isinstance(results,list) or len(results)!=1 or not isinstance(results[0],dict):
        raise Stage3GenerationTrustError("offline attestation verifier returned an ambiguous result set")
    verification=results[0].get("verificationResult"); statement=verification.get("statement") if isinstance(verification,dict) else None
    if not isinstance(statement,dict) or statement.get("predicateType") != profile.accepted_predicate_type:
        raise Stage3GenerationTrustError("offline attestation predicate type mismatch")
    subjects=statement.get("subject")
    if not isinstance(subjects,list) or len(subjects)!=1 or not isinstance(subjects[0],dict) or not isinstance(subjects[0].get("digest"),dict) or subjects[0]["digest"].get("sha256") != evidence_sha256:
        raise Stage3GenerationTrustError("offline attestation subject digest mismatch")
    expected_predicate={"schema_version":"executor-stage3-generation-attestation-predicate/1.0","provider_generation_evidence_schema":_EVIDENCE_SCHEMA,"provider_generation_evidence_sha256":evidence_sha256,"verification_request_sha256":expected_request_sha256}
    if statement.get("predicate") != expected_predicate:
        raise Stage3GenerationTrustError("offline attestation predicate payload mismatch")
    return sha256_bytes(completed.stdout)


def verify_provider_generation_binding(*, evidence_path: str|Path, attestation_bundle_path: str|Path, frozen_result: dict[str,Any], stage2_result: dict[str,Any], proposal: dict[str,Any]) -> TrustedProviderGenerationBinding:
    profile=_load_profile(); evidence_file=Path(evidence_path); bundle_file=Path(attestation_bundle_path)
    evidence,raw=read_canonical_json(evidence_file,label="ProviderGenerationEvidence")
    try: bundle_bytes=bundle_file.read_bytes()
    except OSError as exc: raise Stage3GenerationTrustError("provider attestation bundle is unavailable") from exc
    if not bundle_bytes: raise Stage3GenerationTrustError("provider attestation bundle is empty")
    evidence_sha=sha256_bytes(raw)
    request_sha=_validate_evidence_semantics(evidence,raw=raw,profile=profile,frozen_result=frozen_result,stage2_result=stage2_result,proposal=proposal)
    gh_sha=_verify_attestation_offline(evidence_path=evidence_file,bundle_path=bundle_file,evidence_sha256=evidence_sha,profile=profile,expected_request_sha256=request_sha)
    return TrustedProviderGenerationBinding(copy.deepcopy(evidence),evidence_sha,sha256_bytes(bundle_bytes),request_sha,profile,gh_sha)
