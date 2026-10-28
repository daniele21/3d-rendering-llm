"""No-cloud name-only native ablation integrity tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.evaluation.native_name_ablation import run, NativeAblationError
from geometry_harness.evaluation.rejection_postmortem import TASK_IDS, inspect


def fixture(root):
    bundle = root / "original"
    ablation = root / "name-only"
    ablation.mkdir()
    rows = []
    for i, task in enumerate(TASK_IDS):
        folder = bundle / "tasks" / task
        folder.mkdir(parents=True)
        source = (
            "import bpy\n"
            f"bpy.ops.mesh.primitive_cube_add(size=1,location=({i},0,1))\n"
            "obj=bpy.context.object\n"
            f'obj.name="Part {i} Center"\n'
            "obj.dimensions=(1,1,1)\n"
        )
        path = folder / "model-generated.py"
        path.write_text(source)
        detail, candidate = inspect(source)
        assert candidate and detail["name_ablation_status"] == "COMPILER_PASS_AFTER_NAME_ABLATION"
        derived = ablation / f"{task}.alias-ablation.py"
        derived.write_text(candidate)
        rows.append({"task_id":task, "original_source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                     **detail, "derived_candidate_filename":derived.name})
    (ablation / "postmortem.json").write_text(json.dumps({
        "source_model":"gpt-6-luna", "source_task_count":6,
        "source_native_pass":2, "source_run_status":"INCOMPLETE",
        "source_model_cost_usd_estimate":"0.004875300", "results":rows
    }))
    return bundle, ablation


FAKE_AUDIT = {"original_run_status":"INCOMPLETE",
              "model_estimated_usd":"0.004875300"}


class NativeAblationPreflightTests(unittest.TestCase):
    def test_tampered_derived_source_fails_before_blender_and_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            bundle,ablation=fixture(root)
            target=ablation/f"{TASK_IDS[1]}.alias-ablation.py"
            target.write_text(target.read_text()+"\nimport os\n")
            with patch("geometry_harness.evaluation.native_name_ablation.audit",
                       return_value=FAKE_AUDIT),patch(
                "geometry_harness.evaluation.native_name_ablation.blender_binary") as blender:
                with self.assertRaisesRegex(NativeAblationError,"deterministic name-only"):
                    run(bundle,ablation,root/"derived-native")
                blender.assert_not_called()
            self.assertFalse((root/"derived-native").exists())

    def test_original_source_tampering_fails_before_blender(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            bundle,ablation=fixture(root)
            raw=bundle/"tasks"/TASK_IDS[0]/"model-generated.py"
            raw.write_text(raw.read_text()+"\n# changed\n")
            with patch("geometry_harness.evaluation.native_name_ablation.audit",
                       return_value=FAKE_AUDIT):
                with self.assertRaisesRegex(NativeAblationError,"Original generated code changed"):
                    run(bundle,ablation,root/"derived-native")

    def test_no_incorrect_original_evidence_reclassification(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            bundle,ablation=fixture(root)
            with patch("geometry_harness.evaluation.native_name_ablation.audit",
                       return_value=FAKE_AUDIT),patch(
                "geometry_harness.evaluation.native_name_ablation.blender_binary",
                return_value=None):
                with self.assertRaisesRegex(NativeAblationError,"Real Blender required"):
                    run(bundle,ablation,root/"derived-native")
            self.assertFalse((root/"derived-native").exists())

if __name__ == "__main__":
    unittest.main()
