from pathlib import Path


def test_manual_exact_ref_workflow_uses_dispatch_sha_for_controller_binding():
    workflow = Path(".github/workflows/manual-exact-ref-verify.yml").read_text(encoding="utf-8")

    assert "WORKFLOW_SHA: ${{ github.sha }}" in workflow
    assert "WORKFLOW_REF: ${{ github.ref }}" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "github.workflow_sha" not in workflow
