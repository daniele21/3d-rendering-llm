"""Real Mac Blender dry-run of the historical name-only ablation workflow.

Uses SYNTHETIC safe code only. This CI lane must not read user's private GCS,
execute LLM-generated Python, access API keys or make model requests.
"""
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from geometry_harness.evaluation.native_name_ablation import run
from geometry_harness.evaluation.rejection_postmortem import TASK_IDS, inspect


class NativeNameAblationBlenderTests(unittest.TestCase):
    def test_three_named_candidates_become_native_blender_scenes(self):
        root = Path(os.environ.get("GEOMETRY_NATIVE_ALIAS_FIXTURE_DIR",
                                   "ci-artifacts/showcase/name-only-fixture")).resolve()
        self.assertFalse(root.exists(), "Immutable fixture directory must be new")
        bundle, ablation = root / "synthetic-original", root / "synthetic-aliases"
        ablation.mkdir(parents=True)
        tasks = []
        source_digests = {}
        for task, raw_name in zip(
            TASK_IDS, ("Glass Base Panel", "Upholstered seat cushion",
                       "Bottle - main body")
        ):
            target = bundle / "tasks" / task
            target.mkdir(parents=True)
            raw = (
                "import bpy\n"
                "bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))\n"
                "obj=bpy.context.object\n"
                f"obj.name={raw_name!r}\n"
                "obj.dimensions=(1,1,1)\n"
            )
            original_file = target / "model-generated.py"
            original_file.write_text(raw)
            finding, candidate = inspect(raw)
            self.assertEqual(finding["name_ablation_status"],"COMPILER_PASS_AFTER_NAME_ABLATION")
            candidate_file = ablation / f"{task}.alias-ablation.py"
            candidate_file.write_text(candidate)
            digest = hashlib.sha256(original_file.read_bytes()).hexdigest()
            source_digests[task] = digest
            tasks.append({"task_id": task, "original_source_sha256": digest,
                          **finding, "derived_candidate_filename": candidate_file.name})
        (ablation / "postmortem.json").write_text(json.dumps({
            "source_model": "gpt-6-luna", "source_task_count": 6,
            "source_native_pass": 2, "source_run_status": "INCOMPLETE",
            "source_model_cost_usd_estimate": "0.004875300",
            "results": tasks,
        }))
        with patch("geometry_harness.evaluation.native_name_ablation.audit",
                   return_value={"original_run_status":"INCOMPLETE",
                                 "model_estimated_usd":"0.004875300"}) as auditor:
            result=run(bundle, ablation, root / "derived")
            auditor.assert_called_once_with(bundle)
        self.assertEqual(result["derived_native_pass"],3)
        self.assertEqual(result["counterfactual_native_scene_pass_total"],5)
        self.assertEqual(result["historical_native_scene_pass"],2)
        self.assertEqual(result["new_model_calls"],0)
        self.assertEqual(result["quality_status"],"UNKNOWN_NOT_SHAPE_SCORED")
        for task in TASK_IDS:
            source=bundle/"tasks"/task/"model-generated.py"
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             source_digests[task])
            native=root/"derived"/"tasks"/task/"native"
            self.assertEqual((native/"scene.blend").read_bytes()[:7],b"BLENDER")
            self.assertGreater((native/"preview.png").stat().st_size,100)
            verified=json.loads(
                (root/"derived"/"tasks"/task/"reopened-geometry.json").read_text())
            self.assertTrue(verified["passed"])
            self.assertEqual(len(verified["mesh_objects"]),1)
        self.assertEqual(result["original_run_reclassified"],False)


if __name__=="__main__":
    unittest.main()
