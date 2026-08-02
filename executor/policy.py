from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Any

from executor.sandbox.command_policy import CommandDenied, validate_argv
from executor.sandbox.spec import CommandRule


class ObjectionKind(StrEnum):
    PASS = "PASS"
    CONCERN = "CONCERN"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    POLICY_VETO = "POLICY_VETO"
    HARD_VETO = "HARD_VETO"


HARD_VETO_EVIDENCE = {"missing_required_file", "repository_access_denied", "baseline_hash_changed", "forbidden_path_modified", "required_test_missing", "capability_denied", "contract_invalid"}


@dataclass(frozen=True)
class Objection:
    kind: ObjectionKind
    summary: str
    evidence_type: str | None = None
    evidence: dict[str, Any] | None = None
    minimal_resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "summary": self.summary, "evidence_type": self.evidence_type, "evidence": self.evidence or {}, "minimal_resolution": self.minimal_resolution}


def hard_veto(*, summary: str, evidence_type: str, evidence: dict[str, Any], minimal_resolution: str) -> Objection:
    if evidence_type not in HARD_VETO_EVIDENCE:
        raise ValueError(f"Unsupported HARD_VETO evidence: {evidence_type}")
    if not evidence:
        raise ValueError("HARD_VETO requires evidence")
    return Objection(ObjectionKind.HARD_VETO, summary, evidence_type, evidence, minimal_resolution)


def normalize_model_objection(payload: dict[str, Any]) -> Objection:
    requested = str(payload.get("kind", "CONCERN"))
    summary = str(payload.get("summary", "Model concern"))
    evidence_type = payload.get("evidence_type")
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    resolution = payload.get("minimal_resolution")
    if requested == "HARD_VETO":
        return Objection(
            ObjectionKind.EVIDENCE_GAP,
            summary,
            str(evidence_type) if evidence_type else None,
            evidence,
            "A model cannot self-certify HARD_VETO; a deterministic policy or verifier must produce it.",
        )
    try:
        kind = ObjectionKind(requested)
    except ValueError:
        kind = ObjectionKind.CONCERN
    return Objection(kind, summary, str(evidence_type) if evidence_type else None, evidence, str(resolution) if resolution else None)


def classify_path(project_contract: dict[str, Any], path: str) -> tuple[str, str, str]:
    rules = project_contract["path_rules"]
    for pattern, rule in rules.items():
        if pattern != "**" and fnmatch(path, pattern):
            return pattern, str(rule["class"]), str(rule["approval"])
    rule = rules["**"]
    return "**", str(rule["class"]), str(rule["approval"])


def wrap_repository_content(*, repository: str, commit: str, path: str, content: str, project_contract: dict[str, Any]) -> dict[str, Any]:
    target = PurePosixPath(path).as_posix()
    role = None
    for item in project_contract.get("authoritative_sources", []):
        if PurePosixPath(str(item.get("path", ""))).as_posix() == target:
            role = item.get("role")
            break
    if role == "authoritative_instruction":
        trust, can_instruct = "trusted_project_instruction", True
    elif role in {"state_owner", "evidence"}:
        trust, can_instruct = "trusted_project_data", False
    else:
        trust, can_instruct = "untrusted_data", False
    return {"source_type": "repository_file", "trust": trust, "can_instruct_executor": can_instruct, "cannot_override": ["executor_policy", "project_contract", "task_contract"], "repository": repository, "commit": commit, "path": target, "content": content}


class PolicyEngine:
    def __init__(self, project_contract: dict[str, Any], executor_policy: dict[str, Any] | None = None):
        self.contract = project_contract
        self.executor_policy = executor_policy or {
            "execution": {
                "default_network": False,
                "default_secrets": [],
                "auto_merge": False,
                "external_projects": False,
            }
        }

    def check_path_change(self, path: str, *, public_api_change: bool = False, data_schema_change: bool = False, result_semantics_change: bool = False) -> Objection:
        pattern, path_class, approval = classify_path(self.contract, path)
        if approval == "USER":
            return Objection(ObjectionKind.POLICY_VETO, f"{path} requires USER approval", "path_policy", {"path": path, "pattern": pattern, "class": path_class}, "Request owner approval or choose an AI-approved path.")
        checks = {"public_api_change": public_api_change, "data_schema_change": data_schema_change, "result_semantics_change": result_semantics_change}
        impact = self.contract.get("change_impact_rules", {})
        blocked = [name for name, active in checks.items() if active and impact.get(name) == "USER"]
        if blocked:
            return Objection(ObjectionKind.POLICY_VETO, f"Technical path escalated by semantic impact: {', '.join(blocked)}", "change_impact", {"path": path, "impact": blocked}, "Request USER approval or redesign.")
        return Objection(ObjectionKind.PASS, f"Path change allowed: {path}", evidence={"path": path, "class": path_class})

    def check_forbidden_path(self, path: str, allowed_patterns: list[str]) -> Objection:
        if any(fnmatch(path, pattern) for pattern in allowed_patterns):
            return Objection(ObjectionKind.PASS, f"Path within task scope: {path}")
        return hard_veto(summary=f"Path outside task scope: {path}", evidence_type="forbidden_path_modified", evidence={"path": path, "allowed_patterns": allowed_patterns}, minimal_resolution="Revert path or extend scope through approved task contract.")

    def check_capabilities(self, *, network: bool = False, secrets: list[str] | None = None, command: str | None = None) -> list[Objection]:
        objections: list[Objection] = []
        caps = self.contract["capabilities"]
        execution = self.executor_policy.get("execution", {})
        project_network = caps["network"]["default"] is True
        policy_network = execution.get("default_network") is True
        if network and not (project_network and policy_network):
            objections.append(hard_veto(summary="Network capability denied", evidence_type="capability_denied", evidence={"capability": "network", "requested": True, "project_allowed": project_network, "policy_allowed": policy_network}, minimal_resolution="Use offline method or owner-approved policy and contract."))
        project_secrets = set(caps["secrets"]["default"])
        policy_secrets = set(execution.get("default_secrets", []))
        allowed_secrets = project_secrets & policy_secrets
        for secret in secrets or []:
            if secret not in allowed_secrets:
                objections.append(hard_veto(summary=f"Secret capability denied: {secret}", evidence_type="capability_denied", evidence={"capability": "secret", "name": secret, "project_allowed": sorted(project_secrets), "policy_allowed": sorted(policy_secrets)}, minimal_resolution="Remove request or obtain authorization in both policy and project contract."))
        if command:
            try:
                argv = shlex.split(command)
            except ValueError:
                argv = []
            rules_payload = caps["commands"].get("rules", [])
            if rules_payload:
                rules = tuple(CommandRule.from_dict(item) for item in rules_payload)
                try:
                    validate_argv(argv, rules)
                except CommandDenied as exc:
                    objections.append(hard_veto(summary=str(exc), evidence_type="capability_denied", evidence={"capability": "command", "argv": argv}, minimal_resolution="Use a command matching an approved executable and argv prefix."))
            else:
                executable = argv[0] if argv else ""
                allowed = set(caps["commands"]["allow"])
                if executable not in allowed:
                    objections.append(hard_veto(summary=f"Command denied: {executable or '<invalid>'}", evidence_type="capability_denied", evidence={"capability": "command", "command": command, "allowed": sorted(allowed)}, minimal_resolution="Use allowed command or update contract."))
        return objections or [Objection(ObjectionKind.PASS, "Requested capabilities are allowed")]
