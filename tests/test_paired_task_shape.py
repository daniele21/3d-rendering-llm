"""Offline mocked contracts for new frozen per-task RNG Chamfer protocol."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.evaluation.counterfactual_shape import ORIGINAL_VALID, TASK_IDS
from geometry_harness.evaluation.paired_task_shape import _score_one, run, POINTS, SEED
from geometry_harness.evaluation.upstream_shape_adapter import ShapeGateError, UPSTREAM_COMMIT

MODEL = "gpt-6-luna"


def fake_metric(task, cd):
    return {"model": MODEL, "n_instances": 1, "n_ok": 1,
            "n_points": POINTS, "normalization": "unit_sphere",
            "yaw_alignment": [0, 90, 180, 270],
            "per_instance": [{
                "instance": task, "status": "OK",
                "n_ref_pts": POINTS, "n_gen_pts": POINTS,
                "cd": cd, "cd_yawmin": cd, "yaw_argmin": 0,
            }]}


class PairedTaskScoreTests(unittest.TestCase):
    def test_identical_seed_runs_once_per_task_and_uses_isolated_results(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scorer = root / "shape_chamfer.py"
            scorer.write_text("# synthetic scorer fixture")
            mesh = root / "mesh.glb"
            mesh.write_bytes(b"glTF" + b"x" * 10)
            def scorer_process(command, **kwargs):
                self.assertEqual(command[command.index("--seed") + 1], str(SEED))
                self.assertEqual(command[command.index("--n-points") + 1], str(POINTS))
                self.assertEqual(len(command[command.index("--instances") + 1:
                                             command.index("--n-points")]), 1)
                task = command[command.index("--instances") + 1]
                result_root = Path(command[command.index("--results-root") + 1])
                metric = result_root/MODEL/"_metrics"/"shape_chamfer.json"
                metric.parent.mkdir()
                metric.write_text(json.dumps(fake_metric(task, .031)))
                return SimpleNamespace(returncode=0,stdout="ok",stderr="")
            with patch("geometry_harness.evaluation.paired_task_shape.subprocess.run",
                       side_effect=scorer_process):
                first = _score_one(scorer, root, root/"a", "Bottle_seed0", mesh)
                second = _score_one(scorer, root, root/"b", "Bottle_seed0", mesh)
            self.assertEqual(first["cd"], second["cd"])
            self.assertEqual(first["cd_yawmin"], second["cd_yawmin"])
            self.assertEqual(first["generated_glb_sha256"], second["generated_glb_sha256"])
            self.assertEqual(first["status"], "OK")
            self.assertTrue((root/"a"/"scorer-stdout.txt").is_file())

    def test_one_task_missing_generated_glb_never_reports_ok(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scorer = root / "scorer.py"
            scorer.write_text("# stub")
            source = root / "mesh.glb"
            source.write_bytes(b"glTFfake")
            def score_missing(command, **kwargs):
                target = Path(command[command.index("--results-root")+1])
                metric = target/MODEL/"_metrics"/"shape_chamfer.json"
                metric.parent.mkdir()
                payload = fake_metric("Bottle_seed0", .02)
                payload["n_ok"] = 0
                payload["per_instance"][0]["status"] = "BAD_GEN_MESH"
                metric.write_text(json.dumps(payload))
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            with patch("geometry_harness.evaluation.paired_task_shape.subprocess.run",
                       side_effect=score_missing):
                with self.assertRaisesRegex(ShapeGateError,"Unexpected pinned one-task metric"):
                    _score_one(scorer, root, root/"out", "Bottle_seed0", source)

    def test_full_new_protocol_five_vs_two_exact_shared_scenes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original, stage, upstream, out = [root/x for x in ("original","stage","upstream","out")]
            script = b"# reviewed scorer\n"
            (upstream/"metrics").mkdir(parents=True)
            (upstream/"metrics"/"shape_chamfer.py").write_bytes(script)
            original.mkdir()
            stage.mkdir()
            original_glbs, candidate_glbs, rows = {}, {}, []
            for task in EXPECTED_IDS:
                rec = {"task_id":task,"generated_glb":None}
                if task != "BrainCoral_seed0":
                    path = stage/f"{task}.glb"
                    path.write_bytes(b"glTF" + task.encode())
                    rec["generated_glb"] = {
                        "path":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                        "bytes":path.stat().st_size}
                    candidate_glbs[task] = path
                    if task in ORIGINAL_VALID:
                        original_file = original/f"{task}.glb"
                        original_file.write_bytes(path.read_bytes())
                        original_glbs[task] = original_file
                rows.append(rec)
            (stage/"scorer-staging.json").write_text(json.dumps({
                "expected_tasks":list(EXPECTED_IDS),"tasks":rows}))
            original_report = {"source_sha":"old-sha","dataset_revision":"old-dataset"}
            old_provenance = {
                "upstream_shape_scorer_sha256":hashlib.sha256(script).hexdigest(),
                "reference_glb_sha256":[{"task_id":t,"sha256":"a"*64}
                                        for t in EXPECTED_IDS]}
            validated = {"shape_status":"DESCRIPTIVE_5_SCENES_NOT_PAIRED",
                         "frozen_scorer_matches":True,"frozen_references_match":True,
                         "five_scene_coverage_confirmed":True}
            scorer_count=[]
            def score_one(command, **kwargs):
                if command[0] == "git":
                    return SimpleNamespace(stdout=script)
                self.assertIn("--instances",command)
                self.assertEqual(command[command.index("--seed")+1], str(SEED))
                task=command[command.index("--instances")+1]
                scorer_count.append(task)
                cd = .04 if task in ORIGINAL_VALID else .02
                folder=Path(command[command.index("--results-root")+1])/MODEL/"_metrics"
                folder.mkdir()
                (folder/"shape_chamfer.json").write_text(json.dumps(fake_metric(task, cd)))
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")
            with patch("geometry_harness.evaluation.paired_task_shape.diagnose_existing",
                       return_value=validated), patch(
                "geometry_harness.evaluation.paired_task_shape._preflight",
                return_value=(original_report,old_provenance,{},original_glbs,{})), patch(
                "geometry_harness.evaluation.paired_task_shape.subprocess.run", side_effect=score_one):
                result=run(original,original,original,stage,upstream,root,out)
            self.assertEqual(result["status"],"PER_TASK_RNG_ISOLATED_REPRODUCIBLE")
            self.assertEqual(result["n_baseline_scored"],2)
            self.assertEqual(result["n_candidate_scored"],5)
            self.assertEqual(len(scorer_count),7)
            self.assertTrue(result["baseline_shared_tasks_exact_match"])
            self.assertEqual(result["counterfactual_native_pass"],5)
            self.assertEqual(len(result["per_instance"]),6)
            self.assertEqual(next(r for r in result["per_instance"]
                                  if r["task_id"]=="BrainCoral_seed0")["cd"],None)
            self.assertTrue((out/"paired-one-task-chamfer.json").is_file())
            with self.assertRaisesRegex(ShapeGateError,"never overwrite"):
                run(original,original,original,stage,upstream,root,out)

    def test_unverified_frozen_provenance_never_creates_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("geometry_harness.evaluation.paired_task_shape.diagnose_existing",
                       return_value={"shape_status":"UNKNOWN_PROVENANCE_OR_COHORT_FAILED"}):
                with self.assertRaisesRegex(ShapeGateError,"Untrusted historical"):
                    run(root,root,root,root,root,root,root/"out")
            self.assertFalse((root/"out").exists())


if __name__ == "__main__":
    unittest.main()
