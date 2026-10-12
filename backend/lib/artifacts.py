"""Canonical artifact paths: 1 plan → 1 case.yaml → 1 case.e2e.spec.ts."""

from pathlib import Path

CASE_YAML_NAME = "case.yaml"
CASE_SPEC_NAME = "case.e2e.spec.ts"


def testcase_path(root: Path, plan_id: str) -> Path:
    return root / "tests" / "testcases" / plan_id / CASE_YAML_NAME


def spec_path(root: Path, plan_id: str) -> Path:
    return root / "tests" / "scripts" / "e2e" / plan_id / CASE_SPEC_NAME


def testcase_rel(plan_id: str) -> str:
    return f"tests/testcases/{plan_id}/{CASE_YAML_NAME}"


def spec_rel(plan_id: str) -> str:
    return f"tests/scripts/e2e/{plan_id}/{CASE_SPEC_NAME}"
