"""Security and provenance gates for the opt-in Bottle cone experiment."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.evaluation.cone_counterfactual import (
    run, CounterfactualError,
)
from geometry_harness.evaluation.local_staged_blender import StagedBlenderError
from geometry_harness.providers.local import DEFAULT_MODEL
from geometry_harness.benchmark_smoke import EXPECTED_REV
from geometry_harness.strategies.bpy_subset import (
    compile_bpy_subset, UnsafeGeneratedCode,
)

BOTTLE = """bpy.ops.mesh.primitive_cone_add(radius1=2, radius2=0.5, depth=4, vertices=32, location=(0, 0, 2))
obj = bpy.context.object
obj.name = "bottle_body"
bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1, vertices=32, location=(0, 0, 4.5))
obj = bpy.context.object
obj.name = "bottle_neck"
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, segments=16, ring_count=16, location=(0, 0, 5.5))
obj = bpy.context.object
obj.name = "bottle_cap"
bpy.ops.mesh.primitive_cylinder_add(radius=1.8, depth=0.2, vertices=32, location=(0, 0, 2))
obj = bpy.context.object
obj.name = "label_band"
"""

TABLE = """import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))
obj = bpy.context.object
obj.name = "tabletop"
obj.dimensions = (2,1,0.1)
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_fixture(root: Path):
    stage = root / "stage"
    baseline = root / "baseline"
    stage.mkdir()
    baseline.mkdir()
    rows=[]
    for task, text, state in [
        ("CoffeeTable_seed0", TABLE, "PASS"),
        ("Bottle_seed0", BOTTLE, "FAIL"),
    ]:
        d=stage/"tasks"/task
        d.mkdir(parents=True)
        code=d/"model-generated.py"
        code.write_text(text)
        files=[{"path":str(code.relative_to(stage)), "sha256":sha(code),"bytes":code.stat().st_size}]
        if state=="PASS":
            spec=d/"scene-spec.json"
            spec.write_text(json.dumps(compile_bpy_subset(text,normalize_names=True)))
            files.append({"path":str(spec.relative_to(stage)), "sha256":sha(spec),"bytes":spec.stat().st_size})
        rows.append({
            "task_id":task, "provider_status":"COMPLETED",
            "safe_source":state, "native_scene":"UNKNOWN",
            "error_class":"UnsafeGeneratedCode" if state=="FAIL" else None,
            "files":files
        })
    (stage/"local-benchmark.json").write_text(json.dumps({
        "phase":"GENERATION_ONLY_REQUIRES_LATER_BLENDER",
        "runtime":"korgis_loopback_only",
        "dataset_revision":EXPECTED_REV,
        "model":DEFAULT_MODEL,
        "task_ids":["CoffeeTable_seed0","Bottle_seed0"],
        "safe_source_pass":1,
        "new_model_calls":2,
        "result_rows":rows,
    }))
    (baseline/"local-blender-validation.json").write_text(json.dumps({
        "stage_report_sha256":sha(stage/"local-benchmark.json"),
        "runtime":"NO_KORGIS_REQUESTS_BLENDER_ONLY",
        "model_calls":0, "model":DEFAULT_MODEL,
        "attempted":2,"native_pass":1,
        "per_instance":[
            {"task_id":"CoffeeTable_seed0","native_scene":"PASS"},
            {"task_id":"Bottle_seed0","native_scene":"UNKNOWN"},
        ],
    }))
    return stage, baseline


class ConeParserSecurityTests(unittest.TestCase):
    def test_original_contract_rejects_real_bottle(self):
        with self.assertRaisesRegex(UnsafeGeneratedCode,"Unsupported Blender operation"):
            compile_bpy_subset(BOTTLE,normalize_names=True)
        s=compile_bpy_subset(BOTTLE,normalize_names=True,allow_cone=True)
        self.assertEqual([x["kind"] for x in s["objects"]],
                         ["cone","cylinder","uv_sphere","cylinder"])
        c=s["objects"][0]
        self.assertEqual(c["radius1"],2.)
        self.assertEqual(c["radius2"],.5)
        self.assertEqual(c["dimensions"],[4.,4.,4.])
        self.assertFalse(s["source_execution"])

    def test_cone_bounded_and_requires_valid_literal(self):
        for source in (
            "bpy.ops.mesh.primitive_cone_add(radius1=-1,radius2=1)",
            "bpy.ops.mesh.primitive_cone_add(radius1=0,radius2=0)",
            "bpy.ops.mesh.primitive_cone_add(radius1=16,radius2=0)",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=1,vertices=65)",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=1,vertices=2)",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=1,depth=999)",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=1,depth=-1)",
            "bpy.ops.mesh.primitive_cone_add(radius1=True,radius2=1)",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=float('nan'))",
            "bpy.ops.mesh.primitive_cone_add(radius1=1)",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=0,material=1)",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=0,location=(31,0,0))",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=0)\nimport os",
            "bpy.ops.mesh.primitive_cone_add(radius1=1,radius2=0)\nfor i in range(1):\n  pass",
        ):
            with self.subTest(source=source), self.assertRaises(UnsafeGeneratedCode):
                compile_bpy_subset(source,allow_cone=True)
        with self.assertRaises(UnsafeGeneratedCode):
            compile_bpy_subset(BOTTLE,allow_cone="yes")
        tip=compile_bpy_subset(
            "bpy.ops.mesh.primitive_cone_add(radius1=0,radius2=1,depth=1)",
            allow_cone=True,
        )
        self.assertEqual(tip["objects"][0]["dimensions"],[2.,2.,1.])


class PosthocReplayTests(unittest.TestCase):
    def test_provenance_and_independent_native_pass_without_model(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,baseline=stage_fixture(root)
            old_sha=sha(stage/"local-benchmark.json")
            def fake_blender(_binary, folder):
                (folder/"scene.blend").write_bytes(b"BLENDER")
                (folder/"preview.png").write_bytes(b"fake preview")
                (folder/"geometry.json").write_text(json.dumps({"passed":True}))
            with patch("geometry_harness.evaluation.cone_counterfactual._build_and_reopen",
                       side_effect=fake_blender) as invoked:
                result=run(stage,baseline,root/"derived",binary="/fake/blender")
            self.assertEqual(invoked.call_count,1)
            self.assertEqual(result["counterfactual_native_scene"],"PASS")
            self.assertEqual(result["post_hoc_combined_native_pass"],2)
            self.assertTrue(result["post_hoc_not_original_model_success"])
            self.assertEqual(result["new_model_calls"],0)
            self.assertEqual(result["cone_count"],1)
            self.assertEqual(result["generated_mesh_objects"],4)
            self.assertEqual(result["source_model_output_sha256"],
                             result["replayed_model_output_sha256"])
            self.assertEqual(sha(stage/"local-benchmark.json"),old_sha)
            self.assertFalse((stage/"tasks"/"Bottle_seed0"/"scene-spec.json").exists())
            self.assertFalse((baseline/"cone-counterfactual.json").exists())

    def test_baseline_tamper_blocks_replay_before_blender(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,baseline=stage_fixture(root)
            doc=json.loads((baseline/"local-blender-validation.json").read_text())
            doc["stage_report_sha256"]="0"*64
            (baseline/"local-blender-validation.json").write_text(json.dumps(doc))
            with patch("geometry_harness.evaluation.cone_counterfactual._build_and_reopen") as call:
                with self.assertRaisesRegex(CounterfactualError, "does not match"):
                    run(stage,baseline,root/"derived",binary="/fake/blender")
                call.assert_not_called()
            self.assertFalse((root/"derived").exists())

    def test_generated_source_sha_tamper_blocks_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,baseline=stage_fixture(root)
            (stage/"tasks"/"Bottle_seed0"/"model-generated.py").write_text(
                "import os\nos.system('echo unsafe')"
            )
            with patch("geometry_harness.evaluation.cone_counterfactual._build_and_reopen") as call:
                with self.assertRaisesRegex(StagedBlenderError,"hash/bytes mismatch"):
                    run(stage,baseline,root/"derived",binary="/fake/blender")
                call.assert_not_called()
            self.assertFalse((root/"derived").exists())

    def test_wrong_original_failure_kind_is_not_reclassified(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,baseline=stage_fixture(root)
            baseline_report=stage/"local-benchmark.json"
            data=json.loads(baseline_report.read_text())
            data["result_rows"][1]["error_class"]="TimeoutError"
            baseline_report.write_text(json.dumps(data))
            valid=json.loads((baseline/"local-blender-validation.json").read_text())
            valid["stage_report_sha256"]=sha(baseline_report)
            (baseline/"local-blender-validation.json").write_text(json.dumps(valid))
            with self.assertRaisesRegex(CounterfactualError,"original AST rejection"):
                run(stage,baseline,root/"derived",binary="/fake/blender")


if __name__=="__main__":
    unittest.main()
