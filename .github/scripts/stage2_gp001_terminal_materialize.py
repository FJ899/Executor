from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from executor.github_trust import canonical_json
from executor.solution_provider import (
    SolutionProvider,
    SolutionProviderError,
    VerifiedGenerationEvidence,
)

MODEL = "gpt-5.6-sol"
PROVIDER = "OpenAI"
VERIFICATION_METHOD = "OPENAI_RESPONSES_RETRIEVE_V1"
RESPONSES_BASE = "https://api.openai.com/v1"
MAX_PROVIDER_BYTES = 16 * 1024 * 1024


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def utc_from_provider(value: Any) -> str:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise RuntimeError("provider created_at is invalid")
    generated = dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
    return generated.isoformat(
        timespec="microseconds" if generated.microsecond else "seconds"
    ).replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError("challenge timestamp is invalid")
    return dt.datetime.fromisoformat(value[:-1] + "+00:00").astimezone(dt.timezone.utc)


def one_text(items: Any, kind: str) -> str:
    values: list[str] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == kind
                    and isinstance(part.get("text"), str)
                ):
                    values.append(part["text"])
    if len(values) != 1:
        raise RuntimeError(f"provider record must contain exactly one {kind}")
    return values[0]


class OpenAIReadClient:
    def __init__(self, credential: str) -> None:
        if not isinstance(credential, str) or not credential.strip():
            raise RuntimeError("OPENAI_API_KEY is unavailable")
        self._credential = credential.strip()

    def _request(self, method: str, path: str, *, payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
        data = None
        headers = {
            "Authorization": "Bearer " + self._credential,
            "Accept": "application/json",
            "User-Agent": "FJ899-Executor-Stage2-Terminal-Materializer/1.0",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            RESPONSES_BASE + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read(MAX_PROVIDER_BYTES + 1)
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            detail = exc.read(8192).decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail[:2000]}") from exc
        except OSError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc
        if len(raw) > MAX_PROVIDER_BYTES:
            raise RuntimeError("OpenAI response exceeds size bound")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("OpenAI returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("OpenAI returned non-object JSON")
        return value, response_headers

    def create(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        return self._request("POST", "/responses", payload=payload)

    def get_response(self, response_id: str) -> dict[str, Any]:
        quoted = urllib.parse.quote(response_id, safe="")
        value, _ = self._request("GET", "/responses/" + quoted)
        return value

    def get_input_items(self, response_id: str) -> dict[str, Any]:
        quoted = urllib.parse.quote(response_id, safe="")
        value, _ = self._request("GET", "/responses/" + quoted + "/input_items?limit=100")
        if value.get("has_more") is True:
            raise RuntimeError("provider input-items pagination is incomplete")
        return value


class OpenAIResponsesGenerator:
    provider = PROVIDER
    model = MODEL

    def __init__(self, client: OpenAIReadClient, output_dir: pathlib.Path) -> None:
        self._client = client
        self._output_dir = output_dir

    def generate(self, prompt: dict[str, Any]) -> dict[str, Any]:
        prompt_text = canonical_json(prompt)
        challenge = prompt.get("generation_challenge")
        if not isinstance(challenge, dict):
            raise RuntimeError("generation challenge missing from prompt")
        issued_at = parse_utc(challenge.get("issued_at"))

        # Provider created_at is retrieved as Unix seconds. Do not weaken the frozen
        # generated_at > challenge.issued_at invariant: wait until a later whole
        # second before creating the provider record.
        not_before = math.floor(issued_at.timestamp()) + 1.05
        delay = not_before - time.time()
        if delay > 0:
            time.sleep(delay)

        schema = {
            "type": "object",
            "properties": {
                "schema_version": {
                    "type": "string",
                    "enum": ["executor-solution-generation/1.1"],
                },
                "mutations": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "enum": ["project_registry/registry.py"],
                            },
                            "replacement_text": {"type": "string"},
                        },
                        "required": ["path", "replacement_text"],
                        "additionalProperties": False,
                    },
                },
                "rationale": {"type": "string"},
            },
            "required": ["schema_version", "mutations", "rationale"],
            "additionalProperties": False,
        }
        request_payload = {
            "model": self.model,
            "input": prompt_text,
            "store": True,
            "reasoning": {"effort": "high"},
            "max_output_tokens": 16000,
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "executor_solution_generation",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        response, headers = self._client.create(request_payload)
        response_id = response.get("id")
        if not isinstance(response_id, str) or not response_id.startswith("resp_"):
            raise RuntimeError("OpenAI response id is invalid")

        metadata = {
            "schema_version": "executor-stage2-provider-call-metadata/1.0",
            "provider": PROVIDER,
            "requested_model": self.model,
            "response_id": response_id,
            "response_model": response.get("model"),
            "response_status": response.get("status"),
            "provider_created_at": response.get("created_at"),
            "provider_generated_at": utc_from_provider(response.get("created_at")),
            "x_request_id": headers.get("x-request-id"),
            "prompt_sha256": sha256_bytes(prompt_text.encode("utf-8")),
            "store": True,
        }
        (self._output_dir / "provider-call-metadata.json").write_text(
            canonical_json(metadata), encoding="utf-8"
        )

        if response.get("status") != "completed":
            raise RuntimeError(f"OpenAI response did not complete: {response.get('status')}")
        if response.get("model") != self.model:
            raise RuntimeError("OpenAI response model identity mismatch")
        output_text = one_text(response.get("output"), "output_text")
        try:
            generation = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI output_text is not JSON") from exc
        if not isinstance(generation, dict):
            raise RuntimeError("OpenAI output_text must be a JSON object")
        generation = copy.deepcopy(generation)
        rationale = generation.get("rationale")
        if isinstance(rationale, str):
            generation["rationale"] = rationale.strip()
        generation["evidence_ref"] = response_id
        return generation


class OpenAIResponsesVerifier:
    def __init__(self, client: OpenAIReadClient) -> None:
        self._client = client

    def verify(self, evidence_ref: str) -> VerifiedGenerationEvidence:
        response = self._client.get_response(evidence_ref)
        inputs = self._client.get_input_items(evidence_ref)
        if response.get("id") != evidence_ref or response.get("status") != "completed":
            raise RuntimeError("stored provider response identity/status mismatch")
        if response.get("model") != MODEL:
            raise RuntimeError("stored provider response model mismatch")

        input_text = one_text(inputs.get("data"), "input_text")
        try:
            prompt = json.loads(input_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("stored provider prompt is not JSON") from exc
        if not isinstance(prompt, dict) or input_text != canonical_json(prompt):
            raise RuntimeError("stored provider prompt is not exact canonical JSON")
        if prompt.get("schema_version") != "executor-solution-provider-prompt/1.2":
            raise RuntimeError("stored provider prompt schema mismatch")

        context = prompt.get("source_context")
        challenge = prompt.get("generation_challenge")
        target = prompt.get("target")
        if not isinstance(context, dict) or not isinstance(challenge, dict) or not isinstance(target, dict):
            raise RuntimeError("stored provider prompt binding is incomplete")

        context_material = {
            key: copy.deepcopy(value)
            for key, value in context.items()
            if key != "context_sha256"
        }
        context_sha = sha256_json(context_material)
        if context_sha != context.get("context_sha256"):
            raise RuntimeError("stored provider source-context hash mismatch")

        output_text = one_text(response.get("output"), "output_text")
        try:
            raw_generation = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("stored provider output is not JSON") from exc
        if not isinstance(raw_generation, dict):
            raise RuntimeError("stored provider output is not an object")
        mutations = raw_generation.get("mutations")
        rationale = raw_generation.get("rationale")
        if not isinstance(mutations, list) or not isinstance(rationale, str):
            raise RuntimeError("stored provider output fields are invalid")
        response_sha = sha256_json(
            {
                "schema_version": raw_generation.get("schema_version"),
                "mutations": copy.deepcopy(mutations),
                "rationale": rationale.strip(),
            }
        )
        return VerifiedGenerationEvidence(
            evidence_ref=evidence_ref,
            provider=PROVIDER,
            model=MODEL,
            generated_at=utc_from_provider(response.get("created_at")),
            frozen_contract_sha256=prompt.get("frozen_contract_sha256"),
            repository=context.get("repository"),
            commit=context.get("commit"),
            tree=context.get("tree"),
            context_sha256=context_sha,
            prompt_sha256=sha256_bytes(input_text.encode("utf-8")),
            response_sha256=response_sha,
            generation_challenge_sha256=sha256_json(challenge),
            generation_challenge_issued_at=challenge.get("issued_at"),
            freeze_receipt_sha256=challenge.get("freeze_receipt_sha256"),
            verification_method=VERIFICATION_METHOD,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-result", required=True)
    parser.add_argument("--checkout-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_path = pathlib.Path(args.frozen_result)
    frozen_raw = frozen_path.read_bytes()
    frozen_result = json.loads(frozen_raw.decode("utf-8"))
    if not isinstance(frozen_result, dict):
        raise RuntimeError("frozen result must be a JSON object")

    client = OpenAIReadClient(os.environ.get("OPENAI_API_KEY", ""))
    generator = OpenAIResponsesGenerator(client, output_dir)
    verifier = OpenAIResponsesVerifier(client)
    provider = SolutionProvider(generator, verifier)
    result = provider.provide(
        frozen_result=frozen_result,
        checkout_root=args.checkout_root,
    )

    stage2 = result.to_dict()
    proposal = copy.deepcopy(result.proposal)
    if stage2.get("effect_capability") != "NONE":
        raise RuntimeError("Stage-2 terminal materialization unexpectedly carries effect authority")
    (output_dir / "stage2-terminal-result.json").write_text(
        canonical_json(stage2), encoding="utf-8"
    )
    (output_dir / "validated-solution-proposal.json").write_text(
        canonical_json(proposal), encoding="utf-8"
    )
    receipt = {
        "schema_version": "executor-stage2-terminal-materialization-receipt/1.0",
        "status": stage2.get("status"),
        "effect_capability": stage2.get("effect_capability"),
        "provider": stage2.get("provider"),
        "model": stage2.get("model"),
        "generation_evidence_ref": stage2.get("generation_evidence_ref"),
        "frozen_result_sha256": sha256_bytes(frozen_raw),
        "stage2_terminal_result_sha256": sha256_bytes(
            canonical_json(stage2).encode("utf-8")
        ),
        "proposal_payload_sha256": stage2.get("proposal_sha256"),
        "target_repository_write_count": 0,
        "stage3_effect_executed": False,
        "human_stage3_effect_authority_consumed": False,
    }
    (output_dir / "stage2-materialization-receipt.json").write_text(
        canonical_json(receipt), encoding="utf-8"
    )
    print(canonical_json(receipt))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SolutionProviderError, RuntimeError, OSError, ValueError) as exc:
        print(f"STAGE2_TERMINAL_MATERIALIZATION_BLOCK: {exc}")
        raise SystemExit(2)
