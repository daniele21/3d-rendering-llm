"""No-cost, no-Python-execution, fail-closed historic Luna parser postmortem."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.evaluation.rejection_postmortem import inspect, run, PostmortemError, TASK_IDS
from geometry_harness.strategies.bpy_subset import compile_bpy_subset

PREFIX = """import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))
obj = bpy.context.object
obj.name = %s
obj.dimensions = (1,1,1)
"""


class NameOnlyAblationTests(unittest.TestCase):
    def test_only_name_strings_change_and_strict_parser_is_still_used(self):
        raw = PREFIX % "'Glass Bottle'"
        report, candidate = inspect(raw)
        self.assertEqual(report["original_compiler_error"], "Invalid or unsafe geometry name")
        self.assertEqual(report["name_ablation_status"], "COMPILER_PASS_AFTER_NAME_ABLATION")
        self.assertEqual(report["candidate_object_count"], 1)
        self.assertEqual(report["invalid_names"][0]["suggested_alias"], "Glass_Bottle")
        self.assertEqual(compile_bpy_subset(candidate)["objects"][0]["name"], "Glass_Bottle")
        self.assertEqual(report["native_scene_after_ablation"], "NOT_RUN")
        self.assertNotIn("Glass_Bottle", raw)

    def test_other_unsafe_code_stays_rejected_after_name_repair(self):
        raw = PREFIX % "'Glass Bottle'"
        raw += "\nbpy.ops.wm.open_mainfile(filepath='/tmp/untrusted.blend')\n"
        report, candidate = inspect(raw)
        self.assertEqual(report["name_ablation_status"], "COMPILER_FAIL_AFTER_NAME_ABLATION")
        self.assertIsNone(candidate)
        self.assertEqual(report["name_ablation_compiler_error"], "Unsupported Blender operation")

    def test_invalid_control_character_path_rejected_not_sanitized(self):
        report, candidate = inspect(PREFIX % "'../secret/path'")
        self.assertEqual(report["name_ablation_status"], "BLOCKED_UNSAFE_NAME")
        self.assertIsNone(candidate)
        self.assertEqual(report["native_scene_after_ablation"], "NOT_RUN")

    def test_alias_collision_rejected_instead_of_changing_other_objects(self):
        source = PREFIX % "'Part 1'"
        source += PREFIX % "'Part_1'"
        report, candidate = inspect(source)
        self.assertEqual(report["name_ablation_status"], "BLOCKED_COLLIDING_ALIAS")
        self.assertIsNone(candidate)

    def test_valid_code_has_no_reclassified_score(self):
        report, candidate = inspect(PREFIX % "'valid_part'")
        self.assertEqual(report["original_compiler_status"], "COMPILER_PASS")
        self.assertEqual(report["name_ablation_status"], "NOT_APPLICABLE_NO_INVALID_LITERAL_NAMES")
        self.assertIsNone(candidate)

    def test_operator_diagnostic_keeps_original_bundle_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private = root / "private"
            for task in TASK_IDS:
                target = private / "tasks" / task
                target.mkdir(parents=True)
                (target / "model-generated.py").write_text(PREFIX % "'My Item'")
            fake_audit = {"original_run_status": "INCOMPLETE",
                          "audit_status": "EVIDENCE_VERIFIED_NOT_UPSTREAM_SCORED",
                          "model": "gpt-6-luna",
                          "dataset_revision": "b70b4ee54b93fab76596da5809f3e71c617fa5c2",
                          "native_pass": 2, "task_count": 6,
                          "model_estimated_usd": "0.004875300"}
            with patch("geometry_harness.evaluation.rejection_postmortem.audit",
                       return_value=fake_audit) as audited:
                report = run(private, root / "derivative")
                audited.assert_called_once()
            self.assertEqual(report["postmortem_model_calls"], 0)
            self.assertEqual(report["source_native_pass"], 2)
            self.assertEqual(len(report["results"]), 3)
            self.assertTrue(all(r["name_ablation_status"] == "COMPILER_PASS_AFTER_NAME_ABLATION"
                                for r in report["results"]))
            self.assertIn("My Item", (private/"tasks"/TASK_IDS[0]/"model-generated.py").read_text())
            self.assertEqual((root/"derivative"/"postmortem.json").stat().st_mode & 0o777, 0o600)
            with patch("geometry_harness.evaluation.rejection_postmortem.audit",
                       return_value=fake_audit), self.assertRaises(PostmortemError):
                run(private, root / "derivative")


if __name__ == "__main__":
    unittest.main()
