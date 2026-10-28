"""Counterfactual scorer offline gates: preserve original, never fake missing scores."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.evaluation.counterfactual_shape import (
    ORIGINAL_VALID, TASK_IDS, _paired_metrics, run,
)
from geometry_harness.evaluation.upstream_shape_adapter import ShapeGateError, UPSTREAM_COMMIT


def metrics(*, changed=False, missing=False):
    rows = []
    for task in EXPECTED_IDS:
        ok = task in ORIGINAL_VALID or task in TASK_IDS
        if missing and task == TASK_IDS[0]:
            ok = False
        cd = .04215983617482963 if task == "CoffeeTable_seed0" else .6346081023071021
        if changed and task == "CoffeeTable_seed0":
            cd += .1
        rows.append({"instance": task, "status": "OK" if ok else "NO_GEN_GLB",
                     "cd": cd if ok else None,
                     "cd_yawmin": cd if ok else None})
    return {"n_instances": 6, "n_ok": sum(x["status"] == "OK" for x in rows),
            "per_instance": rows, "cd": {"conditional_mean": .3, "penalized_mean": .6}}


class CounterfactualScoringTests(unittest.TestCase):
    def test_original_pair_reproducibility_is_mandatory(self):
        original = metrics(missing=True)
        original["n_ok"] = 2
        # Baseline only has two genuine results.
        for row in original["per_instance"]:
            if row["instance"] not in ORIGINAL_VALID:
                row.update(status="NO_GEN_GLB", cd=None, cd_yawmin=None)
        self.assertTrue(_paired_metrics(metrics(), original))
        self.assertFalse(_paired_metrics(metrics(changed=True), original))
        self.assertFalse(_paired_metrics(missing=True), original))
        self.assertFalse(_paired_metrics({**metrics(), "n_ok": 2}, original))
        self.assertFalse(_paired_metrics({**metrics(), "per_instance": []}, original))

    def test_no_private_inputs_never_creates_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            target = p / "output"
            with self.assertRaises(ValueError):
                run(p/"missing-original", p/"missing-stage", p/"missing-derived", target)
            self.assertFalse(target.exists())

    def test_refuses_to_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            output = p / "already"
            output.mkdir()
            with self.assertRaisesRegex(ShapeGateError, "never overwrite"):
                run(p/"missing", p/"missing", p/"missing", output)

    def test_stage_and_scoring_keep_five_fixed_denominator(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original, baseline, derived, out = (root/x for x in ("original", "baseline", "derived", "out"))
            for x in (original, baseline, derived):
                x.mkdir()
            origins = {}
            for task in ORIGINAL_VALID:
                g = baseline / f"{task}.glb"
                g.write_bytes(b"glTF" + task.encode())
                origins[task] = g
            recovered = {}
            for task in TASK_IDS:
                scene = derived / f"{task}.blend"
                scene.write_bytes(b"BLENDER" + task.encode())
                recovered[task] = (scene, [f"part_{task}"])
            old = metrics()
            for entry in old["per_instance"]:
                if entry["instance"] not in ORIGINAL_VALID:
                    entry.update(status="NO_GEN_GLB", cd=None, cd_yawmin=None)
            old["n_ok"] = 2
            old_provenance = {
                "upstream_commit": UPSTREAM_COMMIT,
                "upstream_shape_scorer_sha256": "a" * 64,
                "reference_glb_sha256": [{"task_id": t, "sha256": "b" * 64} for t in EXPECTED_IDS],
            }
            def fake_export(cmd, log_path, limit=120):
                dest = Path(cmd[cmd.index("--out") + 1])
                dest.write_bytes(b"glTFderived")
                log_path.write_text("audited exporter")
            def fake_score(output, upstream, refs):
                target = output / "results" / "text_to_3D" / "gpt-6-luna" / "_metrics"
                target.mkdir()
                (target/"shape_chamfer.json").write_text(json.dumps(metrics()))
                (output/"shape-scorer-provenance.json").write_text(json.dumps({
                    **old_provenance, "scorer_status": "UPSTREAM_SHAPE_CHAMFER_EXECUTED"
                }))
            preflight_result = (
                {"source_sha": "abc", "dataset_revision": "pinned", "original_run_status": "INCOMPLETE",
                 "model_estimated_usd": "0.004875300"},
                old_provenance, old, origins, recovered,
            )
            with patch("geometry_harness.evaluation.counterfactual_shape._preflight",
                       return_value=preflight_result), patch(
                "geometry_harness.evaluation.counterfactual_shape.blender_binary", return_value="/fake/blender"), patch(
                "geometry_harness.evaluation.counterfactual_shape._safe_run", side_effect=fake_export
            ) as exported, patch(
                "geometry_harness.evaluation.counterfactual_shape.score", side_effect=fake_score):
                result = run(original, baseline, derived, out, upstream=root, refs=root)
            self.assertEqual(exported.call_count, 3)
            self.assertEqual(result["shape_status"], "SCORED_PINNED_COUNTERFACTUAL")
            self.assertEqual(result["n_scored"], 5)
            self.assertEqual(json.loads((out/"scorer-staging.json").read_text())["native_pass"], 5)
            self.assertFalse((baseline/"scorer-staging.json").exists())
            self.assertEqual(len(result["per_instance"]), 6)
            self.assertIsNone(next(x for x in result["per_instance"]
                                   if x["instance"] == "BrainCoral_seed0")["cd"])


if __name__ == "__main__":
    unittest.main()
