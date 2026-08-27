from __future__ import annotations

import copy
import json
import os
import re
import secrets
import stat
import time
from fnmatch import fnmatch
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from executor.frozen_pilot_authority import FrozenPilotAuthorityError, validate_frozen_pilot_authority
from executor.github_trust import canonical_json
from executor.solution_proposal import SolutionProposalError, ValidatedSolutionProposal, validate_solution_proposal
from executor.stage3_authority import (
    P1_STAGE3_ID, P1_STAGE3_SHA256, STAGE3_ACTION, AuthorityConsumption, Stage3AuthorityError,
    authority_is_unused, build_terminal_authority_receipt, consume_authority_once,
    validate_human_stage3_effect_authorization,
)
from executor.stage3_evidence import (
    Manifest, Stage3EvidenceError, build_git_manifest, build_repository_manifest, canonical_patch_identity,
    changed_paths, durable_write_json, git_manifest_identities, read_canonical_json, sha256_bytes, sha256_json,
    validate_external_negative_observation,
)
from executor.stage3_generation_trust import (
    Stage3GenerationTrustError, TrustedProviderGenerationBinding, runtime_trust_bundle_sha256,
    verify_provider_generation_binding,
)
from executor.stage3_workspace import (
    Stage3WorkspaceError, TargetSnapshot, apply_exact_descriptor_replacement, open_validated_target_readonly,
    reopen_target_for_effect, verify_pinned_clean_workspace,
)


class Stage3RuntimeError(ValueError): pass


class Stage3TerminalStatus(str, Enum):
    BLOCK="BLOCK"; FAIL="FAIL"; UNKNOWN="UNKNOWN"; MUTATION_APPLIED_REVIEW_REQUIRED="MUTATION_APPLIED_REVIEW_REQUIRED"


@dataclass(frozen=True)
class Stage3RunResult:
    terminal_status: Stage3TerminalStatus
    evidence_bundle_path: str|None
    evidence_bundle_sha256: str|None
    authority_consumed: bool
    repository_write_count_claim: int|None
    detail: str


P2_PARENT_ID="P2-STAGE3-ARCH-001@1.0"
P2_PARENT_SHA256="28abb40b6290d8720ba5beed56ee89f020e927bc21dc636a8819d1942cbdd2db"
P2_AMENDMENT_ID="P2-STAGE3-ARCH-001@1.1"
P2_AMENDMENT_SHA256="4857d353cfbddac240617c1cc473d4c902aaac1471fc828a1c11d06934febb3c"
P3_BASE_COMMIT="0c6db09653c41c3287e43c2111e590663050c02c"
P3_BASE_TREE="b0526b3c06690e23ed84d11c6ab7a70d4e86137e"
ALLOCATION_ROOT=Path("/workspace"); REPOSITORY_PLANE=ALLOCATION_ROOT/"repo"; CONTROL_PLANE=ALLOCATION_ROOT/".stage3-control"; INPUTS=CONTROL_PLANE/"inputs"; RECEIPTS=CONTROL_PLANE/"receipts"
P1_ARTIFACT=INPUTS/"P1-STAGE3-001_v1.0.md"; FROZEN_RESULT_INPUT=INPUTS/"frozen-task-result.json"; STAGE2_RESULT_INPUT=INPUTS/"stage2-terminal-result.json"; PROPOSAL_INPUT=INPUTS/"validated-solution-proposal.json"; PROVIDER_EVIDENCE_INPUT=INPUTS/"provider-generation-evidence.json"; PROVIDER_ATTESTATION_INPUT=INPUTS/"provider-attestation-bundle.json"; HUMAN_AUTHORITY_INPUT=INPUTS/"human-stage3-effect-authorization.json"; ENVIRONMENT_INPUT=INPUTS/"environment.json"
HOST_OBSERVER_OUTPUT=CONTROL_PLANE/"observer"/"stage3-host-observation.json"
IMMUTABLE_INPUT_PATHS=(P1_ARTIFACT,FROZEN_RESULT_INPUT,STAGE2_RESULT_INPUT,PROPOSAL_INPUT,PROVIDER_EVIDENCE_INPUT,PROVIDER_ATTESTATION_INPUT,HUMAN_AUTHORITY_INPUT,ENVIRONMENT_INPUT)
WORKER_STOPPED_RECEIPT=RECEIPTS/"worker-stopped.json"; EVIDENCE_BUNDLE_OUTPUT=RECEIPTS/"stage3-evidence-bundle.json"; TERMINAL_RECEIPT=RECEIPTS/"stage3-terminal.json"
OBSERVER_WAIT_SECONDS=15.0; OBSERVER_POLL_SECONDS=0.05
_ENV_SCHEMA="executor-stage3-environment/1.0"; _ENV_HASH_CONSTRUCTION="SHA256_CANONICAL_JSON_WITHOUT_BOUNDED_ENVIRONMENT_SHA256"
_SAFE_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,191}$"); _SHA256=re.compile(r"^[0-9a-f]{64}$"); _GIT_SHA=re.compile(r"^[0-9a-f]{40}$"); _IMAGE_DIGEST=re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class _Environment:
    workspace_instance_id:str; target_repository:str; implementation_commit:str; implementation_tree:str
    runtime_image_digest:str; trust_bundle_sha256:str; bounded_environment_sha256:str; raw:dict[str,Any]


def _assert_immutable_regular(path:Path, *, label:str)->bytes:
    try: info=path.lstat()
    except OSError as exc: raise Stage3RuntimeError(f"{label} is unavailable") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or stat.S_ISLNK(info.st_mode): raise Stage3RuntimeError(f"{label} is not an immutable regular input object")
    if stat.S_IMODE(info.st_mode)&0o222: raise Stage3RuntimeError(f"{label} is writable and therefore not an immutable input object")
    try: return path.read_bytes()
    except OSError as exc: raise Stage3RuntimeError(f"{label} cannot be read") from exc


def _read_immutable_json(path:Path, *, label:str)->tuple[dict[str,Any],bytes]:
    raw=_assert_immutable_regular(path,label=label)
    try: value=json.loads(raw.decode("utf-8"))
    except (UnicodeError,json.JSONDecodeError) as exc: raise Stage3RuntimeError(f"{label} is not UTF-8 JSON") from exc
    if not isinstance(value,dict): raise Stage3RuntimeError(f"{label} must be a JSON object")
    if canonical_json(value).encode("utf-8")!=raw: raise Stage3RuntimeError(f"{label} is not canonical JSON")
    return value,raw


def _immutable_input_manifest()->dict[str,Any]:
    entries=[]
    for path in IMMUTABLE_INPUT_PATHS:
        raw=_assert_immutable_regular(path,label=f"immutable control input {path.name}")
        entries.append({"path":path.relative_to(CONTROL_PLANE).as_posix(),"size":len(raw),"sha256":sha256_bytes(raw)})
    entries.sort(key=lambda item:item["path"]); material={"schema_version":"executor-stage3-control-input-manifest/1.0","entries":entries}
    return {**material,"root_sha256":sha256_json(material)}


def _validate_p1_artifact()->None:
    if sha256_bytes(_assert_immutable_regular(P1_ARTIFACT,label="frozen P1 Stage-3 Task Contract"))!=P1_STAGE3_SHA256: raise Stage3RuntimeError("frozen P1 Stage-3 Task Contract content identity mismatch")


def _validate_stage2_result(stage2:dict[str,Any], *, proposal:dict[str,Any], validated:ValidatedSolutionProposal)->str:
    expected={"schema_version","status","provider","model","context_sha256","prompt_sha256","generation_challenge_sha256","generation_challenge_issued_at","generation_evidence_ref","generation_response_sha256","proposal_sha256","effect_capability","proposal"}
    if set(stage2)!=expected: raise Stage3RuntimeError("Stage-2 terminal result has invalid fields")
    if stage2.get("schema_version")!="executor-solution-provider-result/1.2": raise Stage3RuntimeError("Stage-2 terminal result schema mismatch")
    if stage2.get("status")!="VALIDATED_SOLUTION_PROPOSAL": raise Stage3RuntimeError("Stage-2 terminal status does not authorize Stage-3 consideration")
    if stage2.get("effect_capability")!="NONE": raise Stage3RuntimeError("Stage-2 terminal result unexpectedly carries effect capability")
    if stage2.get("proposal")!=proposal or stage2.get("proposal_sha256")!=validated.payload_sha256: raise Stage3RuntimeError("Stage-2 terminal result proposal identity mismatch")
    provenance=validated.provenance
    for label,actual,required in (("provider",stage2.get("provider"),provenance.get("provider")),("model",stage2.get("model"),provenance.get("model")),("context",stage2.get("context_sha256"),provenance.get("context_sha256")),("prompt",stage2.get("prompt_sha256"),provenance.get("prompt_sha256")),("challenge",stage2.get("generation_challenge_sha256"),provenance.get("generation_challenge_sha256")),("challenge time",stage2.get("generation_challenge_issued_at"),provenance.get("generation_challenge_issued_at")),("evidence reference",stage2.get("generation_evidence_ref"),provenance.get("generation_evidence_ref")),("response",stage2.get("generation_response_sha256"),provenance.get("generation_response_sha256"))):
        if actual!=required: raise Stage3RuntimeError(f"Stage-2 terminal result {label} binding mismatch")
    for field in ("context_sha256","prompt_sha256","generation_challenge_sha256","generation_response_sha256","proposal_sha256"):
        if not isinstance(stage2.get(field),str) or _SHA256.fullmatch(stage2[field]) is None: raise Stage3RuntimeError(f"Stage-2 terminal result {field} is invalid")
    return sha256_json(stage2)


def _parse_mountinfo_writable_outside_allocation()->list[str]:
    try: lines=Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError as exc: raise Stage3RuntimeError("cannot inspect bounded mount namespace") from exc
    bad=[]; prefix=str(ALLOCATION_ROOT).rstrip("/")+"/"
    for line in lines:
        before,sep,after=line.partition(" - ")
        if not sep: raise Stage3RuntimeError("mount namespace evidence is malformed")
        fields=before.split(); tail=after.split()
        if len(fields)<6 or len(tail)<3: raise Stage3RuntimeError("mount namespace evidence is malformed")
        mount_point=fields[4].replace("\\040"," "); writable="rw" in set(fields[5].split(",")) or "rw" in set(tail[2].split(",")); inside=mount_point==str(ALLOCATION_ROOT) or mount_point.startswith(prefix)
        if writable and not inside: bad.append(mount_point)
    return sorted(set(bad))


def _validate_network_namespace()->None:
    try: interfaces={item.name for item in Path("/sys/class/net").iterdir()}
    except OSError as exc: raise Stage3RuntimeError("cannot inspect bounded network namespace") from exc
    if interfaces-{"lo"}: raise Stage3RuntimeError("Stage-3 mutation environment has a non-loopback network interface")


def _validate_secret_inventory()->None:
    fragments=("TOKEN","SECRET","PASSWORD","CREDENTIAL","API_KEY","PRIVATE_KEY")
    if [key for key,value in os.environ.items() if value and any(fragment in key.upper() for fragment in fragments)]: raise Stage3RuntimeError("Stage-3 mutation environment exposes secret-like environment variables")


def _validate_environment(value:dict[str,Any], *, trust_bundle_sha256:str)->_Environment:
    expected={"schema_version","workspace_instance_id","target_repository","repository_plane","control_plane","network","secrets","writable_mount_scope","worker_isolation","implementation_commit","implementation_tree","runtime_image_digest","runtime_trust_bundle_sha256","environment_hash_construction","bounded_environment_sha256"}
    if set(value)!=expected or value.get("schema_version")!=_ENV_SCHEMA: raise Stage3RuntimeError("bounded Stage-3 environment identity/schema mismatch")
    workspace_id=value.get("workspace_instance_id"); target_repository=value.get("target_repository")
    if not isinstance(workspace_id,str) or _SAFE_ID.fullmatch(workspace_id) is None: raise Stage3RuntimeError("workspace_instance_id is invalid")
    if not isinstance(target_repository,str) or "/" not in target_repository: raise Stage3RuntimeError("bounded target repository identity is invalid")
    exact={"repository_plane":str(REPOSITORY_PLANE),"control_plane":str(CONTROL_PLANE),"network":"NONE","secrets":"NONE","writable_mount_scope":"STAGE3_ALLOCATION_ONLY","worker_isolation":"ONE_FD_SECCOMP_X86_64","runtime_trust_bundle_sha256":trust_bundle_sha256,"environment_hash_construction":_ENV_HASH_CONSTRUCTION}
    for field,required in exact.items():
        if value.get(field)!=required: raise Stage3RuntimeError(f"bounded Stage-3 environment {field} mismatch")
    if not isinstance(value.get("implementation_commit"),str) or _GIT_SHA.fullmatch(value["implementation_commit"]) is None: raise Stage3RuntimeError("implementation commit identity is invalid")
    if not isinstance(value.get("implementation_tree"),str) or _GIT_SHA.fullmatch(value["implementation_tree"]) is None: raise Stage3RuntimeError("implementation tree identity is invalid")
    if not isinstance(value.get("runtime_image_digest"),str) or _IMAGE_DIGEST.fullmatch(value["runtime_image_digest"]) is None: raise Stage3RuntimeError("runtime image digest is invalid")
    claimed=value.get("bounded_environment_sha256"); material=copy.deepcopy(value); material.pop("bounded_environment_sha256")
    if not isinstance(claimed,str) or _SHA256.fullmatch(claimed) is None or sha256_json(material)!=claimed: raise Stage3RuntimeError("bounded environment canonical hash mismatch")
    if _parse_mountinfo_writable_outside_allocation(): raise Stage3RuntimeError("Stage-3 allocation has writable mounts outside /workspace")
    _validate_network_namespace(); _validate_secret_inventory()
    return _Environment(workspace_id,target_repository,value["implementation_commit"],value["implementation_tree"],value["runtime_image_digest"],trust_bundle_sha256,claimed,copy.deepcopy(value))


def _revalidate_exact_mutation_scope(*, frozen_result:dict[str,Any], validated:ValidatedSolutionProposal)->Any:
    if len(validated.mutations)!=1: raise Stage3RuntimeError("Stage 3 requires exactly one proposal mutation")
    contract=frozen_result.get("contract"); task=contract.get("task") if isinstance(contract,dict) else None
    if not isinstance(task,dict): raise Stage3RuntimeError("frozen task scope is unavailable for mutation revalidation")
    allowed=task.get("allowed_paths"); protected=task.get("protected_paths")
    if not isinstance(allowed,list) or not all(isinstance(item,str) for item in allowed): raise Stage3RuntimeError("frozen allowed_paths are invalid")
    if not isinstance(protected,list) or not all(isinstance(item,str) for item in protected): raise Stage3RuntimeError("frozen protected_paths are invalid")
    mutation=validated.mutations[0]
    if mutation.path not in set(allowed) or any(fnmatch(mutation.path,pattern) for pattern in protected): raise Stage3RuntimeError("mutation path is outside the frozen Stage-3 scope")
    if mutation.path==".git" or mutation.path.startswith(".git/"): raise Stage3RuntimeError("Stage 3 may not target Git metadata")
    if sha256_bytes(mutation.replacement_text.encode("utf-8"))!=mutation.expected_after_sha256: raise Stage3RuntimeError("replacement bytes do not match expected after hash")
    return mutation


def _same_target_identity(left:TargetSnapshot,right:TargetSnapshot)->bool:
    return (left.device,left.inode,left.mode,left.uid,left.gid,left.nlink,left.size,left.content_sha256,left.xattrs_sha256)==(right.device,right.inode,right.mode,right.uid,right.gid,right.nlink,right.size,right.content_sha256,right.xattrs_sha256)


def _effect_binding(*, stage2_sha256:str, validated:ValidatedSolutionProposal, mutation:Any, provider_binding:TrustedProviderGenerationBinding, environment:_Environment, authorization_payload_sha256:str)->dict[str,Any]:
    return {"schema_version":"executor-stage3-effect-binding/1.0","stage2_terminal_schema":"executor-solution-provider-result/1.2","stage2_terminal_result_sha256":stage2_sha256,"stage2_terminal_status":"VALIDATED_SOLUTION_PROPOSAL","frozen_stage3_task_contract_id":P1_STAGE3_ID,"frozen_stage3_task_contract_sha256":P1_STAGE3_SHA256,"proposal_id":validated.proposal_id,"proposal_payload_sha256":validated.payload_sha256,"repository":validated.repository,"source_commit":validated.source_commit,"source_tree":validated.source_tree,"mutation_count":1,"mutation_path":mutation.path,"expected_before_sha256":mutation.expected_before_sha256,"expected_after_sha256":mutation.expected_after_sha256,"provider_generation_binding_sha256":provider_binding.binding_sha256,"provider_generation_evidence_sha256":provider_binding.evidence_sha256,"runtime_trust_bundle_sha256":provider_binding.trust_profile.trusted_root_sha256,"runtime_identity_policy_sha256":provider_binding.trust_profile.policy_sha256,"bounded_environment_sha256":environment.bounded_environment_sha256,"workspace_instance_id":environment.workspace_instance_id,"human_effect_authorization_payload_sha256":authorization_payload_sha256,"human_effect_authorization_state":"UNUSED","action":STAGE3_ACTION}


def _safe_post_manifests()->tuple[Manifest|None,Manifest|None]:
    try: return build_repository_manifest(REPOSITORY_PLANE),build_git_manifest(REPOSITORY_PLANE)
    except Exception: return None,None


def _classify_post_consumption_exception(*, pre_repo:Manifest|None, pre_git:Manifest|None, post_repo:Manifest|None, post_git:Manifest|None, mutation:Any|None)->tuple[Stage3TerminalStatus,int|None]:
    if pre_repo is None or pre_git is None or post_repo is None or post_git is None: return Stage3TerminalStatus.UNKNOWN,None
    changed=changed_paths(pre_repo,post_repo); write_claim=len(changed)
    if not changed or mutation is None or changed!=(mutation.path,) or pre_git.root_sha256!=post_git.root_sha256: return Stage3TerminalStatus.FAIL,write_claim
    target={item["path"]:item for item in post_repo.entries}.get(mutation.path)
    if not isinstance(target,dict) or target.get("type")!="regular" or target.get("content_sha256")!=mutation.expected_after_sha256: return Stage3TerminalStatus.FAIL,write_claim
    return Stage3TerminalStatus.UNKNOWN,write_claim


def _write_terminal_receipt(status:Stage3TerminalStatus, *, evidence_sha256:str|None, detail:str)->None:
    if not TERMINAL_RECEIPT.exists(): durable_write_json(TERMINAL_RECEIPT,{"schema_version":"executor-stage3-terminal/1.0","terminal_status":status.value,"evidence_bundle_sha256":evidence_sha256,"detail":detail},exclusive=True)


def _block_or_unknown(*, initial_repo:Manifest|None, initial_git:Manifest|None, detail:str)->Stage3RunResult:
    post_repo,post_git=_safe_post_manifests(); zero=initial_repo is not None and initial_git is not None and post_repo is not None and post_git is not None and initial_repo.root_sha256==post_repo.root_sha256 and initial_git.root_sha256==post_git.root_sha256
    status=Stage3TerminalStatus.BLOCK if zero else Stage3TerminalStatus.UNKNOWN; _write_terminal_receipt(status,evidence_sha256=None,detail=detail)
    return Stage3RunResult(status,None,None,False,0 if zero else None,detail)


def _wait_for_observer(worker_receipt_sha256:str, *, target:str, workspace_instance_id:str)->tuple[dict[str,Any],str]:
    deadline=time.monotonic()+OBSERVER_WAIT_SECONDS
    while time.monotonic()<deadline:
        if HOST_OBSERVER_OUTPUT.exists():
            try:
                info=HOST_OBSERVER_OUTPUT.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)&0o222: raise Stage3EvidenceError("external observer receipt is not immutable")
                value,_=read_canonical_json(HOST_OBSERVER_OUTPUT,label="external host observer receipt")
                digest=validate_external_negative_observation(value,expected_target=target,allocation_root=str(ALLOCATION_ROOT),worker_stopped_receipt_sha256=worker_receipt_sha256,expected_workspace_instance_id=workspace_instance_id)
                return value,digest
            except (OSError,Stage3EvidenceError) as exc: raise Stage3RuntimeError(str(exc)) from exc
        time.sleep(OBSERVER_POLL_SECONDS)
    raise Stage3RuntimeError("independent host observer receipt was not produced after worker stop")


class Stage3MutationRuntime:
    """Dedicated Stage-3 effect runtime. It has no PilotRuntime or caller-verifier surface."""
    def execute(self)->Stage3RunResult:
        if TERMINAL_RECEIPT.exists(): return Stage3RunResult(Stage3TerminalStatus.BLOCK,None,None,False,0,"Stage-3 allocation is already terminal; retry/replay is forbidden")
        initial_repo=initial_git=consumption=pre_repo=pre_git=pre_target=target_fd=None
        worker_started=False; worker_error=None; observed_after=None; observed_byte_count=None; provider_binding=environment=validated=stage2_sha=effect_binding_sha=pre_control_inputs=post_control_inputs=None; mutation=None
        try: initial_repo=build_repository_manifest(REPOSITORY_PLANE); initial_git=build_git_manifest(REPOSITORY_PLANE)
        except Exception: initial_repo=initial_git=None
        try:
            _validate_p1_artifact(); frozen_result,_=_read_immutable_json(FROZEN_RESULT_INPUT,label="frozen Task Contract result")
            try: validate_frozen_pilot_authority(frozen_result)
            except FrozenPilotAuthorityError as exc: raise Stage3RuntimeError(f"frozen Task Contract authority is invalid: {exc}") from exc
            stage2_result,_=_read_immutable_json(STAGE2_RESULT_INPUT,label="Stage-2 terminal result")
            proposal,_=_read_immutable_json(PROPOSAL_INPUT,label="ValidatedSolutionProposal")
            try: validated=validate_solution_proposal(proposal,frozen_result=frozen_result)
            except SolutionProposalError as exc: raise Stage3RuntimeError(f"solution proposal is invalid: {exc}") from exc
            stage2_sha=_validate_stage2_result(stage2_result,proposal=proposal,validated=validated)
            _assert_immutable_regular(PROVIDER_EVIDENCE_INPUT,label="provider generation evidence"); _assert_immutable_regular(PROVIDER_ATTESTATION_INPUT,label="provider attestation bundle")
            provider_binding=verify_provider_generation_binding(evidence_path=PROVIDER_EVIDENCE_INPUT,attestation_bundle_path=PROVIDER_ATTESTATION_INPUT,frozen_result=frozen_result,stage2_result=stage2_result,proposal=proposal)
            workspace_identity,tree_entries=verify_pinned_clean_workspace(REPOSITORY_PLANE,repository=validated.repository,expected_repository=validated.repository,commit=validated.source_commit,tree=validated.source_tree)
            if workspace_identity.commit!=validated.source_commit or workspace_identity.tree!=validated.source_tree: raise Stage3RuntimeError("pinned workspace source identity mismatch")
            pre_repo=build_repository_manifest(REPOSITORY_PLANE); pre_git=build_git_manifest(REPOSITORY_PLANE)
            if initial_repo is not None and initial_repo.root_sha256!=pre_repo.root_sha256: raise Stage3RuntimeError("repository changed during pre-effect validation")
            if initial_git is not None and initial_git.root_sha256!=pre_git.root_sha256: raise Stage3RuntimeError("Git metadata changed during pre-effect validation")
            mutation=_revalidate_exact_mutation_scope(frozen_result=frozen_result,validated=validated); replacement=mutation.replacement_text.encode("utf-8")
            read_fd,pre_target=open_validated_target_readonly(REPOSITORY_PLANE,path=mutation.path,expected_before_sha256=mutation.expected_before_sha256,tree_entries=tree_entries); os.close(read_fd)
            trust_sha=runtime_trust_bundle_sha256(); environment_raw,_=_read_immutable_json(ENVIRONMENT_INPUT,label="bounded Stage-3 environment"); environment=_validate_environment(environment_raw,trust_bundle_sha256=trust_sha)
            if environment.target_repository!=validated.repository: raise Stage3RuntimeError("bounded environment target repository mismatch")
            env_repo=build_repository_manifest(REPOSITORY_PLANE); env_git=build_git_manifest(REPOSITORY_PLANE)
            if env_repo.root_sha256!=pre_repo.root_sha256 or env_git.root_sha256!=pre_git.root_sha256: raise Stage3RuntimeError("repository changed during environment revalidation")
            authority_raw,_=_read_immutable_json(HUMAN_AUTHORITY_INPUT,label="Human Stage-3 effect authorization")
            authority=validate_human_stage3_effect_authorization(authority_raw,frozen_result=frozen_result,stage2_terminal_result_sha256=stage2_sha,repository=validated.repository,source_commit=validated.source_commit,source_tree=validated.source_tree,proposal_id=validated.proposal_id,proposal_payload_sha256=validated.payload_sha256,mutation_path=mutation.path,before_sha256=mutation.expected_before_sha256,after_sha256=mutation.expected_after_sha256,provider_generation_binding_sha256=provider_binding.binding_sha256,runtime_trust_bundle_sha256=provider_binding.trust_profile.trusted_root_sha256,bounded_environment_sha256=environment.bounded_environment_sha256,workspace_instance_id=environment.workspace_instance_id)
            if not authority_is_unused(CONTROL_PLANE,authority.authorization_id): raise Stage3RuntimeError("human Stage-3 effect authorization replay detected")
            effect_binding=_effect_binding(stage2_sha256=stage2_sha,validated=validated,mutation=mutation,provider_binding=provider_binding,environment=environment,authorization_payload_sha256=authority.payload_sha256); effect_binding_sha=sha256_json(effect_binding)
            pre_control_inputs=_immutable_input_manifest()
            immediate_fd,immediate=open_validated_target_readonly(REPOSITORY_PLANE,path=mutation.path,expected_before_sha256=mutation.expected_before_sha256,tree_entries=tree_entries); os.close(immediate_fd)
            if not _same_target_identity(pre_target,immediate): raise Stage3RuntimeError("target identity changed during final pre-effect revalidation")
            consumption=consume_authority_once(control_root=CONTROL_PLANE,authority=authority,effect_binding_sha256=effect_binding_sha)
            target_fd=reopen_target_for_effect(REPOSITORY_PLANE,path=mutation.path,pre_effect=pre_target); worker_started=True
            try: observed_after,observed_byte_count=apply_exact_descriptor_replacement(target_fd,replacement=replacement,expected_after_sha256=mutation.expected_after_sha256,pre_effect=pre_target)
            except Exception as exc: worker_error=f"{type(exc).__name__}: {exc}"
            finally: os.close(target_fd); target_fd=None
            post_repo=build_repository_manifest(REPOSITORY_PLANE); post_git=build_git_manifest(REPOSITORY_PLANE); changed=changed_paths(pre_repo,post_repo); target_read_fd=None
            try: target_read_fd,final_target=open_validated_target_readonly(REPOSITORY_PLANE,path=mutation.path,expected_before_sha256=mutation.expected_after_sha256 if worker_error is None else None,tree_entries=tree_entries)
            except Stage3WorkspaceError: final_target=None
            finally:
                if target_read_fd is not None: os.close(target_read_fd)
            post_control_inputs=_immutable_input_manifest(); control_inputs_unchanged=pre_control_inputs==post_control_inputs
            worker_stopped={"schema_version":"executor-stage3-worker-stopped/1.0","workspace_instance_id":environment.workspace_instance_id,"authorization_id":authority.authorization_id,"consumption_marker_sha256":consumption.marker_sha256,"effect_binding_sha256":effect_binding_sha,"mutation_path":mutation.path,"worker_started":worker_started,"worker_error":worker_error,"post_repository_manifest_root":post_repo.root_sha256,"post_git_manifest_root":post_git.root_sha256,"changed_paths":list(changed),"observer_challenge":secrets.token_hex(32)}
            worker_receipt_sha=durable_write_json(WORKER_STOPPED_RECEIPT,worker_stopped,exclusive=True)
            try: host_observer,host_observer_sha=_wait_for_observer(worker_receipt_sha,target=mutation.path,workspace_instance_id=environment.workspace_instance_id); observer_error=None
            except Stage3RuntimeError as exc: host_observer=None; host_observer_sha=None; observer_error=str(exc)
            exact_repo_delta=changed==(mutation.path,); git_unchanged=pre_git.root_sha256==post_git.root_sha256; exact_after=worker_error is None and observed_after is not None and final_target is not None and observed_after.content_sha256==mutation.expected_after_sha256 and final_target.content_sha256==mutation.expected_after_sha256 and _same_target_identity(observed_after,final_target) and observed_byte_count==len(replacement)
            if exact_repo_delta and git_unchanged and exact_after and control_inputs_unchanged and host_observer is not None: status=Stage3TerminalStatus.MUTATION_APPLIED_REVIEW_REQUIRED; detail="exact authorized one-file replacement observed; correctness not evaluated"; repository_write_count_claim=1
            elif observer_error is not None and exact_repo_delta and git_unchanged and exact_after and control_inputs_unchanged: status=Stage3TerminalStatus.UNKNOWN; detail=observer_error; repository_write_count_claim=1
            else: status=Stage3TerminalStatus.FAIL; detail=worker_error or observer_error or "post-effect invariant violation"; repository_write_count_claim=len(changed)
            patch_sha=canonical_patch_identity(path=mutation.path,before_sha256=pre_target.content_sha256,after_sha256=observed_after.content_sha256 if observed_after is not None else mutation.expected_after_sha256,before_mode=pre_target.mode,after_mode=observed_after.mode if observed_after is not None else pre_target.mode,replacement_byte_length=len(replacement))
            evidence={"schema_version":"executor-stage3-evidence/1.0","identity":{"architecture_parent_id":P2_PARENT_ID,"architecture_parent_sha256":P2_PARENT_SHA256,"architecture_amendment_id":P2_AMENDMENT_ID,"architecture_amendment_sha256":P2_AMENDMENT_SHA256,"p3_base_commit":P3_BASE_COMMIT,"p3_base_tree":P3_BASE_TREE,"implementation_commit":environment.implementation_commit,"implementation_tree":environment.implementation_tree,"runtime_image_digest":environment.runtime_image_digest,"frozen_stage3_task_contract_id":P1_STAGE3_ID,"frozen_stage3_task_contract_sha256":P1_STAGE3_SHA256,"stage2_terminal_result_sha256":stage2_sha,"proposal_id":validated.proposal_id,"proposal_payload_sha256":validated.payload_sha256},"trust":{"runtime_trust_bundle_sha256":provider_binding.trust_profile.trusted_root_sha256,"runtime_identity_policy_sha256":provider_binding.trust_profile.policy_sha256,"provider_attestation_bundle_sha256":provider_binding.attestation_bundle_sha256,"provider_generation_evidence_sha256":provider_binding.evidence_sha256,"provider_generation_binding_sha256":provider_binding.binding_sha256,"provider":provider_binding.evidence["provider"],"model":provider_binding.evidence["model"],"generation_evidence_ref":provider_binding.evidence["generation_evidence_ref"],"human_effect_authorization_id":authority.authorization_id,"human_effect_authorization_payload_sha256":authority.payload_sha256,"human_principal":authority.human_principal,"human_principal_evidence_ref":authority.human_principal_evidence_ref,"authority_consumption":consumption.to_dict()},"environment_and_source":{"bounded_environment_sha256":environment.bounded_environment_sha256,"workspace_instance_id":environment.workspace_instance_id,"repository":validated.repository,"source_commit":validated.source_commit,"source_tree":validated.source_tree,"pre_repository_manifest_root":pre_repo.root_sha256,"pre_git_manifest_root":pre_git.root_sha256,"pre_git_identities":git_manifest_identities(pre_git),"pre_control_input_manifest_root":pre_control_inputs["root_sha256"],"pre_target":pre_target.to_dict()},"effect_and_post_state":{"effect_binding_sha256":effect_binding_sha,"effect_boundary_consumption_marker_sha256":consumption.marker_sha256,"mutation_path":mutation.path,"expected_before_sha256":mutation.expected_before_sha256,"expected_after_sha256":mutation.expected_after_sha256,"observed_after_sha256":observed_after.content_sha256 if observed_after is not None else None,"observed_byte_count":observed_byte_count,"canonical_patch_identity_sha256":patch_sha,"post_repository_manifest_root":post_repo.root_sha256,"post_git_manifest_root":post_git.root_sha256,"post_git_identities":git_manifest_identities(post_git),"post_control_input_manifest_root":post_control_inputs["root_sha256"],"control_inputs_unchanged":control_inputs_unchanged,"changed_paths":list(changed),"worker_stopped_receipt_sha256":worker_receipt_sha,"host_observer_sha256":host_observer_sha,"host_observer_write_set_sha256":sha256_json(host_observer["repository_write_targets"]) if host_observer is not None else None,"host_observer":host_observer,"worker_error":worker_error,"terminal_status":status.value}}
            evidence_sha=durable_write_json(EVIDENCE_BUNDLE_OUTPUT,evidence,exclusive=True); build_terminal_authority_receipt(control_root=CONTROL_PLANE,consumption=consumption,terminal_status=status.value,effect_evidence_sha256=evidence_sha); _write_terminal_receipt(status,evidence_sha256=evidence_sha,detail=detail)
            return Stage3RunResult(status,str(EVIDENCE_BUNDLE_OUTPUT),evidence_sha,True,repository_write_count_claim,detail)
        except (Stage3RuntimeError,Stage3GenerationTrustError,Stage3AuthorityError,Stage3WorkspaceError,Stage3EvidenceError,OSError) as exc:
            if target_fd is not None:
                try: os.close(target_fd)
                except OSError: pass
            detail=f"{type(exc).__name__}: {exc}"
            if consumption is None: return _block_or_unknown(initial_repo=initial_repo,initial_git=initial_git,detail=detail)
            post_repo,post_git=_safe_post_manifests(); status,write_claim=_classify_post_consumption_exception(pre_repo=pre_repo,pre_git=pre_git,post_repo=post_repo,post_git=post_git,mutation=mutation); evidence_sha=None
            if effect_binding_sha is not None:
                minimal={"schema_version":"executor-stage3-evidence/1.0","identity":{"architecture_parent_id":P2_PARENT_ID,"architecture_parent_sha256":P2_PARENT_SHA256,"architecture_amendment_id":P2_AMENDMENT_ID,"architecture_amendment_sha256":P2_AMENDMENT_SHA256,"frozen_stage3_task_contract_id":P1_STAGE3_ID,"frozen_stage3_task_contract_sha256":P1_STAGE3_SHA256},"failure":{"effect_binding_sha256":effect_binding_sha,"authority_consumption":consumption.to_dict(),"worker_started":worker_started,"detail":detail,"terminal_status":status.value}}
                try: evidence_sha=durable_write_json(EVIDENCE_BUNDLE_OUTPUT,minimal,exclusive=True); build_terminal_authority_receipt(control_root=CONTROL_PLANE,consumption=consumption,terminal_status=status.value,effect_evidence_sha256=evidence_sha)
                except Exception: status=Stage3TerminalStatus.UNKNOWN; evidence_sha=None
            _write_terminal_receipt(status,evidence_sha256=evidence_sha,detail=detail)
            return Stage3RunResult(status,str(EVIDENCE_BUNDLE_OUTPUT) if evidence_sha else None,evidence_sha,True,write_claim,detail)
