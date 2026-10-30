"""Offline scorer gates: correct Qwen identity, no reference -> no score."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from geometry_harness.evaluation.local_qwen_shape import _verify_external_scorer
from geometry_harness.evaluation.paired_task_shape import _score_one
from geometry_harness.evaluation.upstream_shape_adapter import ShapeGateError


class QwenShapeTests(unittest.TestCase):
    def test_no_scorer_or_refs_fails_without_fabricated_result(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"upstream").mkdir()
            (root/"refs").mkdir()
            with self.assertRaisesRegex(ShapeGateError,"Missing pinned scorer"):
                _verify_external_scorer(root/"upstream",root/"refs")
            (root/"upstream"/"metrics").mkdir()
            (root/"upstream"/"metrics"/"shape_chamfer.py").write_text("# dummy")
            with patch("geometry_harness.evaluation.local_qwen_shape.subprocess.run",
                       side_effect=OSError("missing git")):
                with self.assertRaisesRegex(ShapeGateError,"Unable to verify"):
                    _verify_external_scorer(root/"upstream",root/"refs")

    def test_qwen_scorer_does_not_mislabel_luna_and_verifies_8192_point_metric(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            model="qwen3-coder-30b-q4km"
            task="CoffeeTable_seed0"
            generated=root/"source.glb"
            generated.write_bytes(b"glTF" + b"\0"*60)
            def fake_subprocess(command, **_):
                self.assertIn("--model",command)
                self.assertEqual(command[command.index("--model")+1],model)
                self.assertEqual(command[command.index("--seed")+1],"0")
                self.assertEqual(command[command.index("--n-points")+1],"8192")
                result_root=Path(command[command.index("--results-root")+1])
                report=result_root/model/"_metrics"/"shape_chamfer.json"
                report.parent.mkdir(parents=True)
                report.write_text(json.dumps({
                    "model":model,"n_instances":1,"n_ok":1,"n_points":8192,
                    "normalization":"unit_sphere",
                    "yaw_alignment":[0,90,180,270],
                    "per_instance":[{
                        "instance":task, "status":"OK", "cd":.11, "cd_yawmin":.09,
                        "n_ref_pts":8192, "n_gen_pts":8192, "yaw_argmin":90,
                    }],
                }))
                return SimpleNamespace(returncode=0,stdout="ok",stderr="")
            with patch("geometry_harness.evaluation.paired_task_shape.subprocess.run",
                       side_effect=fake_subprocess):
                score=_score_one(root/"shape_chamfer.py",root/"private_refs",
                                  root/"scored",task,generated,model=model)
            self.assertEqual(score["cd"],.11)
            self.assertEqual(score["cd_yawmin"],.09)
            self.assertEqual(score["yaw_argmin"],90)
            self.assertIn(model,score["metric_path"])
            self.assertNotIn("gpt-6-luna",score["metric_path"])

    def test_missing_per_instance_metric_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            generated=root/"source.glb"
            generated.write_bytes(b"glTF"+b"\0"*60)
            with patch("geometry_harness.evaluation.paired_task_shape.subprocess.run",
                       return_value=SimpleNamespace(returncode=0,stdout="",stderr="")):
                with self.assertRaisesRegex(ShapeGateError,"did not create metric"):
                    _score_one(root/"scorer.py",root/"refs",
                               root/"score","Bottle_seed0",generated,
                               model="qwen3-coder-30b-q4km")


if __name__=="__main__":
    unittest.main()
