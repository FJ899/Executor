#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SUBJECT='Trigger fresh GP001 ACCEPT-003 product continuation'
if [ "$(git log -1 --format=%s)" != "$EXPECTED_SUBJECT" ]; then
  echo 'ACCEPT-003 harness is disarmed on this commit' >&2
  exit 2
fi

: "${EXECUTOR_GITHUB_EFFECT_TOKEN:?missing EXECUTOR_GITHUB_EFFECT_TOKEN}"
: "${EXECUTOR_GLOBAL_AUTHORITY_TOKEN:?missing EXECUTOR_GLOBAL_AUTHORITY_TOKEN}"
: "${GITHUB_TOKEN:?missing GITHUB_TOKEN}"
case "$EXECUTOR_GITHUB_EFFECT_TOKEN" in github_pat_*|ghp_*) ;; *) echo 'effect token is not PAT-shaped' >&2; exit 2 ;; esac

mkdir -p run-output effect-evidence runs fresh-request

curl -fsS \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: Bearer $EXECUTOR_GITHUB_EFFECT_TOKEN" \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  https://api.github.com/repos/FJ899/executor-pilot-target > "${RUNNER_TEMP}/target-repository.json"
python - <<'PY'
import json, os
from pathlib import Path
v=json.loads(Path(os.environ['RUNNER_TEMP']+'/target-repository.json').read_text())
if v.get('full_name')!='FJ899/executor-pilot-target': raise SystemExit('target token repository mismatch')
p=v.get('permissions') or {}
if p and (p.get('pull') is not True or p.get('push') is not True): raise SystemExit('target token lacks read/write permission')
print('TARGET_TOKEN_REPOSITORY_OK=true')
PY

python -m pip install --no-deps .

curl -fsSL \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  https://api.github.com/repos/FJ899/Executor/actions/artifacts/9623360112/zip \
  -o "${RUNNER_TEMP}/fresh-request.zip"
unzip -q "${RUNNER_TEMP}/fresh-request.zip" -d fresh-request
formation="$(find fresh-request -type f -name formation.json -print -quit)"
receipt="$(find fresh-request -type f -name 'system_write_receipt-*.json' -print -quit)"
attempt_result="$(find fresh-request -type f -name 'external_effect_attempt_result-*.json' -print -quit)"
test -n "$formation" && test -n "$receipt" && test -n "$attempt_result"
cp "$formation" run-output/formation.json

curl -fsS \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  https://api.github.com/repos/FJ899/Executor/issues/90 > "${RUNNER_TEMP}/issue90.json"

python - "$formation" "$receipt" "$attempt_result" "${RUNNER_TEMP}/issue90.json" <<'PY'
import base64, hashlib, json, pathlib, sys
from executor.github_effect_transaction import canonical_effect_bytes
from executor.github_trust import canonical_json
formation=json.load(open(sys.argv[1],encoding='utf-8'))
receipt_path=pathlib.Path(sys.argv[2]); receipt=json.load(open(receipt_path,encoding='utf-8'))
attempt_result=json.load(open(sys.argv[3],encoding='utf-8'))
issue=json.load(open(sys.argv[4],encoding='utf-8'))
canonical=formation.get('canonical_contract_request') or {}
binding=canonical.get('formation_binding') or {}
payload=canonical.get('github_request_payload') or {}
if payload.get('request_id')!='gp001-product-authority-e2e-002': raise SystemExit('fresh request id mismatch')
if payload.get('expires_at')!='2026-08-26T21:59:09Z': raise SystemExit('fresh request expiry mismatch')
issue_payload={'schema_version':'executor-formation-authority-issue/1.0','title':'Executor authority request: gp001-product-authority-e2e-002','body':canonical_json(payload)}
effect_sha=hashlib.sha256(canonical_effect_bytes(issue_payload)).hexdigest()
if receipt.get('kind')!='SYSTEM_WRITE_RECEIPT': raise SystemExit('missing durable write receipt')
rp=receipt.get('payload') or {}
if rp.get('provider')!='GITHUB' or rp.get('action_kind')!='CREATE_ISSUE' or rp.get('target')!='FJ899/Executor': raise SystemExit('receipt identity mismatch')
if rp.get('effect_sha256')!=effect_sha or rp.get('provider_outcome')!='SUCCESS' or rp.get('provider_status')!=201: raise SystemExit('receipt does not prove successful exact CREATE_ISSUE')
if rp.get('object_id')!='90' or rp.get('object_url')!='https://github.com/FJ899/Executor/issues/90': raise SystemExit('receipt object mismatch')
raw=receipt_path.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
if receipt_path.stem.removeprefix('system_write_receipt-')!=digest: raise SystemExit('receipt filename hash mismatch')
ap=attempt_result.get('payload') or {}
if attempt_result.get('kind')!='EXTERNAL_EFFECT_ATTEMPT_RESULT_BINDING' or ap.get('receipt_evidence_sha256')!=digest: raise SystemExit('attempt result/receipt binding mismatch')
if ap.get('provider_outcome')!='SUCCESS' or ap.get('object_id')!='90' or ap.get('object_url')!='https://github.com/FJ899/Executor/issues/90': raise SystemExit('attempt result object mismatch')
response_b64=receipt.get('provider_response_b64')
if isinstance(response_b64,str):
    response=json.loads(base64.b64decode(response_b64,validate=True).decode())
    if response.get('number')!=90 or response.get('title')!=issue_payload['title'] or response.get('body')!=issue_payload['body']: raise SystemExit('write response mismatch')
if issue.get('number')!=90 or issue.get('node_id')!='I_kwDOTpqUf88AAAABOZq8KA' or issue.get('state')!='open': raise SystemExit('Issue 90 identity/state mismatch')
if issue.get('title')!=issue_payload['title'] or issue.get('body')!=issue_payload['body'] or issue.get('html_url')!='https://github.com/FJ899/Executor/issues/90': raise SystemExit('Issue 90 differs from formation payload')
body_sha=hashlib.sha256(issue['body'].encode()).hexdigest()
if body_sha!='78b55f786a17aea61b6727fb4f6172a93cf3a3bbd32e02b98fc038fbe18b35eb': raise SystemExit('Issue 90 body hash mismatch')
observation_ref=f"github:issue:{issue['node_id']}:{body_sha}"
effect={'schema_version':'executor-github-effect-result/1.0','status':'RECOVERED_EXTERNAL_EFFECT','provider':'GITHUB','action_kind':'CREATE_ISSUE','target':'FJ899/Executor','effect_sha256':effect_sha,'attempt_id':ap.get('attempt_id'),'object_id':'90','object_url':'https://github.com/FJ899/Executor/issues/90','observation_ref':observation_ref,'automatic_retry_allowed':False,'external_write_repeated':False,'recovered_from_status':'POST_WRITE_SERIALIZATION_FAILURE'}
transport={'origin':'FORMATION_PUBLISHED_REQUEST','authority':False,'publisher':'EXECUTOR_FORMATION','provider':'GITHUB','action_kind':'CREATE_ISSUE','target':'FJ899/Executor','object_id':'90','object_url':'https://github.com/FJ899/Executor/issues/90','effect_sha256':effect_sha,'observation_ref':observation_ref,'human_decision_required':True,'recovery_class':'POST_WRITE_SERIALIZATION_FAILURE_RECONCILIATION','external_write_repeated':False}
publication={'schema_version':'executor-formation-publication-result/1.1','status':'AWAITING_VERIFIED_HUMAN_DECISION','canonical_contract_request':canonical,'formation_binding':binding,'github_request_payload':payload,'request_transport_provenance':transport,'publication_effect':effect,'manual_request_rewrite_required':False,'executable':False,'recovery':{'kind':'READ_ONLY_RECEIPT_AND_PROVIDER_RECONCILIATION','external_write_repeated':False,'source_run_id':33013131624,'source_artifact_id':9623360112}}
pathlib.Path('run-output/publication.json').write_text(json.dumps(publication,indent=2,sort_keys=True)+'\n')
print('PUBLICATION_RECOVERED_WITHOUT_WRITE=true')
PY

creative-os-product decide \
  --publication run-output/publication.json \
  --profile trust_profiles/github-product-gp001.json \
  --comment 5431116950 \
  --ledger "${RUNNER_TEMP}/product-authority.sqlite3" \
  > run-output/frozen.json
python - <<'PY'
import json
from pathlib import Path
v=json.loads(Path('run-output/frozen.json').read_text())
if v.get('status')!='AUTHORIZED_AND_FROZEN': raise SystemExit(f'freeze failed: {v}')
d=v.get('decision_evidence') or {}
if d.get('comment_id')!=5431116950: raise SystemExit('frozen contract not bound to ACCEPT-003')
if (v.get('request_transport_provenance') or {}).get('object_id')!='90': raise SystemExit('frozen contract not bound to Issue 90')
print('FROZEN_CONTRACT_SHA256='+v['contract_sha256'])
print('DECISION_EXPIRES_AT='+d['expires_at'])
PY

rm -rf target
git init -q target
git -C target remote add origin https://github.com/FJ899/executor-pilot-target.git
git -C target -c protocol.version=2 -c core.hooksPath=/dev/null -c credential.helper= fetch --no-tags --depth=1 origin 3934a94a5eebf750079200589d6dc40e024d44a0
git -C target checkout -q --detach FETCH_HEAD
test "$(git -C target rev-parse HEAD)" = '3934a94a5eebf750079200589d6dc40e024d44a0'
test "$(git -C target rev-parse 'HEAD^{tree}')" = '26d307afcbb3ce72b2911ca44936712c11558c4c'
test -z "$(git -C target status --porcelain)"

python - <<'PY'
import hashlib,json
from pathlib import Path
from executor.solution_provider import generate_validated_solution
from executor.solution_proposal import validate_solution_proposal
frozen=json.loads(Path('run-output/frozen.json').read_text())
p=Path('target/project_registry/registry.py'); source=p.read_text()
old='''    def add_many(self, projects: Iterable[Project]) -> None:\n        """Add projects one by one, leaving earlier writes after a late duplicate."""\n\n        for project in projects:\n            if project.project_id in self._projects:\n                raise DuplicateProjectError(\n                    f"duplicate project_id: {project.project_id}"\n                )\n            self._projects[project.project_id] = project\n'''
new='''    def add_many(self, projects: Iterable[Project]) -> None:\n        """Add a batch atomically after validating all project identifiers."""\n\n        batch = list(projects)\n        seen = set(self._projects)\n        for project in batch:\n            if project.project_id in seen:\n                raise DuplicateProjectError(\n                    f"duplicate project_id: {project.project_id}"\n                )\n            seen.add(project.project_id)\n        for project in batch:\n            self._projects[project.project_id] = project\n'''
if source.count(old)!=1: raise SystemExit('pinned bounded defect block mismatch')
replacement=source.replace(old,new,1); before=hashlib.sha256(source.encode()).hexdigest(); after=hashlib.sha256(replacement.encode()).hexdigest()
contract=frozen['contract']; task=contract['task']; target=contract['target']
class Provider:
    provider_name='OPENAI_CHATGPT'; model_name='chatgpt-session'
    def generate_candidate(self,*,frozen_contract,prompt):
        return {'schema_version':'executor-solution-candidate/1.0','status':'AWAITING_FROZEN_CONTRACT_SHA','proposal_id':'gp001-product-solution-002','repository':target['repository'],'source_commit':target['commit'],'source_tree':target['tree'],'mutations':[{'path':'project_registry/registry.py','expected_before_sha256':before,'replacement_text':replacement,'expected_after_sha256':after}],'rationale':'Validate the complete batch before mutating ProjectRegistry state.','evidence_plan':[*task['postcondition_argv'],*task['regression_argv']]}
validated=generate_validated_solution(provider=Provider(),frozen_result=frozen,prompt='Re-derive the fresh frozen bounded one-file atomic batch fix without changing protected tests.',historical_candidate_relation='SAME_FIX_REDERIVED')
proposal={'schema_version':'executor-solution-proposal/1.0','proposal_id':validated.proposal_id,'contract_sha256':validated.contract_sha256,'repository':validated.repository,'source_commit':validated.source_commit,'source_tree':validated.source_tree,'mutations':[x.to_dict() for x in validated.mutations],'rationale':validated.rationale,'evidence_plan':[list(x) for x in validated.evidence_plan],'provenance':validated.provenance}
validate_solution_proposal(proposal,frozen_result=frozen)
Path('run-output/proposal.json').write_text(json.dumps(proposal,indent=2,sort_keys=True)+'\n')
PY

docker pull python:3.11-slim
image="$(docker image inspect --format='{{.Id}}' python:3.11-slim)"
case "$image" in sha256:????????????????????????????????????????????????????????????????) ;; *) echo 'unexpected image id' >&2; exit 1 ;; esac

creative-os-product execute \
  --frozen run-output/frozen.json \
  --proposal run-output/proposal.json \
  --profile trust_profiles/github-product-gp001.json \
  --ledger "${RUNNER_TEMP}/product-authority.sqlite3" \
  --workspace target \
  --runs-root runs \
  --run-id "gp001-product-accept003-${GITHUB_RUN_ID}" \
  --image "$image" \
  --executor-root . \
  --executor-commit "$(git rev-parse HEAD)" \
  > run-output/pilot-report.json
python - <<'PY'
import json
from pathlib import Path
v=json.loads(Path('run-output/pilot-report.json').read_text())
if v.get('status')!='ACTION_COMPLETED_REVIEW_REQUIRED': raise SystemExit(f"unexpected pilot status: {v.get('status')}")
print('PILOT_STATUS='+v['status'])
PY

creative-os-product publish-draft-pr \
  --frozen run-output/frozen.json \
  --pilot-report run-output/pilot-report.json \
  --profile trust_profiles/github-product-gp001.json \
  --ledger "${RUNNER_TEMP}/product-authority.sqlite3" \
  --evidence-dir effect-evidence \
  --workspace target \
  > run-output/draft-pr-publication.json
python - <<'PY'
import json
from pathlib import Path
v=json.loads(Path('run-output/draft-pr-publication.json').read_text())
if v.get('status')!='DRAFT_PR_CREATED_REVIEW_REQUIRED': raise SystemExit(f"unexpected publication status: {v.get('status')}")
print('DRAFT_PR_STATUS='+v['status'])
print(json.dumps(v,sort_keys=True))
PY
