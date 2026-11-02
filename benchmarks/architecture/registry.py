"""Frozen synthetic architecture MVP registry and separate generator task projection.

Never feed expected outcomes/answer fields to the model. This module does NOT
pretend to execute the 30-case goal or the two future edit acceptance gates.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUITE = ROOT / "suites" / "architecture_mvp_v1.json"
FIXTURES = ROOT / "fixtures" / "architecture_mvp_cases_v1.json"
SOURCE = ROOT / "fixtures" / "source.txt"
KINDS = {"import", "rejection", "edit"}
EXPECTED = {
    "import": "PLAN_SCHEMA_PASS",
    "rejection": "PLAN_SCHEMA_REJECT",
    "edit": "EDIT_GATE_PENDING",
}


class ArchitectureBenchmarkReject(ValueError):
    pass


def read_suite() -> dict:
    return json.loads(SUITE.read_text(encoding="utf-8"))


def verify_registry() -> dict:
    suite = read_suite()
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    original = SOURCE.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if (suite.get("schema") != "architecture_mvp_suite_v1"
            or suite.get("initial_registered") != 10
            or suite.get("target_total") != 30
            or suite.get("source") != "synthetic_public_only"
            or suite.get("groups") != {"import":10,"rejection":10,"edit":10}
            or suite.get("generator_visible_fields") !=
               ["task_id","instruction","fixture_ref"]
            or fixtures.get("source_sha256") != digest
            or fixtures.get("origin") != "SYNTHETIC_ONLY_NOT_REAL_CAD"):
        raise ArchitectureBenchmarkReject("Frozen suite/source contract changed")
    cases = suite.get("cases")
    available = fixtures.get("fixtures")
    if not isinstance(cases,list) or len(cases)!=10 or not isinstance(available,dict):
        raise ArchitectureBenchmarkReject("Initial 10-case registry incomplete")
    ids=set()
    counts={kind:0 for kind in KINDS}
    for task in cases:
        if not isinstance(task,dict) or not {
                "task_id","kind","fixture_ref","instruction","expected_outcome"
                }.issubset(task):
            raise ArchitectureBenchmarkReject("Malformed case")
        task_id=task["task_id"]
        if (type(task_id) is not str or not task_id.startswith("arch_")
                or task_id in ids or task["kind"] not in KINDS
                or task["expected_outcome"] != EXPECTED[task["kind"]]
                or not isinstance(task["instruction"],str)
                or not 20 <= len(task["instruction"]) <= 240
                or task["fixture_ref"] not in available):
            raise ArchitectureBenchmarkReject("Invalid frozen task ID/outcome/fixture")
        ids.add(task_id)
        counts[task["kind"]]+=1
    if counts!={"import":4,"rejection":4,"edit":2}:
        raise ArchitectureBenchmarkReject("Frozen initial 4/4/2 task mix changed")
    for name,plan in available.items():
        if (not isinstance(plan,dict) or
                plan.get("source_sha256") != digest or
                plan.get("schema_version") != 1):
            raise ArchitectureBenchmarkReject(f"Invalid provenance: {name}")
    return {
        "status":"VALID_INITIAL_REGISTRY_NOT_EXECUTION",
        "registered":10,
        "planned":30,
        "executable_edit_gates":0,
        "unimplemented_edit_gates":2,
        "source_sha256":digest,
        "source_type":"SYNTHETIC_NO_REAL_DXF",
        "count_by_kind":counts,
    }


def generator_tasks() -> list[dict]:
    """Task text only; scorer outcomes are intentionally withheld."""
    verify_registry()
    return [
        {key:case[key] for key in ("task_id","instruction","fixture_ref")}
        for case in read_suite()["cases"]
    ]


if __name__=="__main__":
    print(json.dumps(verify_registry(), indent=2))
