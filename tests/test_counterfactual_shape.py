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
        self.assertFalse(_paired_metrics(metrics(missing=True), original))
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
                "geometry_harness.evaluation.counterfactual_shape._precheck_scorer"), patch(
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


    def test_missing_scorer_is_specific_and_fails_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            with patch("geometry_harness.evaluation.counterfactual_shape._preflight") as audit:
                with self.assertRaisesRegex(ShapeGateError, "Pinned scorer not found"):
                    run(p/"original", p/"baseline", p/"derived", p/"out",
                        upstream=p/"incorrect-checkout", refs=p/"refs")
                audit.assert_not_called()
            self.assertFalse((p/"out").exists())

    def test_resume_staged_glbs_without_exporting_again(self):
        import hashlib
        from geometry_harness.evaluation.counterfactual_shape import (
            _validate_resumable_stage, EXPERIMENT,
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "new-cohort"
            base = out / "results" / "text_to_3D" / "gpt-6-luna"
            base.mkdir(parents=True)
            originals, derived = {}, {}
            rows = []
            for task in EXPECTED_IDS:
                target = base / task
                target.mkdir()
                row = {"task_id": task, "native_scene": "FAIL", "generated_glb": None}
                if task != "BrainCoral_seed0":
                    glb = target / "glb" / f"{task}.glb"
                    glb.parent.mkdir()
                    glb.write_bytes(b"glTF" + task.encode())
                    row["native_scene"] = "PASS"
                    row["shape_status"] = "READY_FOR_ISOLATED_REFERENCE_SCORER"
                    row["source_cohort"] = "original" if task in ORIGINAL_VALID else "name_only_derived"
                    row["generated_glb"] = {
                        "path": str(glb.relative_to(out)), "bytes": glb.stat().st_size,
                        "sha256": hashlib.sha256(glb.read_bytes()).hexdigest()}
                    if task in ORIGINAL_VALID:
                        original = root / (task + ".glb")
                        original.write_bytes(glb.read_bytes())
                        originals[task] = original
                    else:
                        expected = [f"part_{task}"]
                        (target/"expected.json").write_text(json.dumps({"object_ids": expected}))
                        (target/"export.log").write_text("trusted fixture export")
                        derived[task] = (root / (task + ".blend"), expected)
                rows.append(row)
            historical = {"source_sha":"hash", "dataset_revision":"revision",
                          "model_estimated_usd":"0.004875300", "original_run_status":"INCOMPLETE"}
            stage = {"schema_version":1, "experiment":EXPERIMENT,
                     "model":"gpt-6-luna","upstream_commit":UPSTREAM_COMMIT,
                     "source_sha":"hash", "dataset_revision":"revision",
                     "source_cost_estimated_usd":"0.004875300",
                     "original_run_status":"INCOMPLETE","original_native_pass":2,
                     "native_pass":5, "model_calls":0,
                     "quality_status":"UNKNOWN_NOT_SHAPE_SCORED",
                     "expected_tasks":list(EXPECTED_IDS),"tasks":rows}
            (out/"scorer-staging.json").write_text(json.dumps(stage))
            self.assertEqual(_validate_resumable_stage(out, historical, originals, derived), stage)
            old = metrics()
            for entry in old["per_instance"]:
                if entry["instance"] not in ORIGINAL_VALID:
                    entry.update(status="NO_GEN_GLB", cd=None, cd_yawmin=None)
            old["n_ok"] = 2
            provenance = {
                "upstream_commit": UPSTREAM_COMMIT,
                "upstream_shape_scorer_sha256": "a" * 64,
                "reference_glb_sha256": [{"task_id": t, "sha256": "b" * 64} for t in EXPECTED_IDS],
            }
            def fake_score(output, upstream, refs):
                target = base / "_metrics"
                target.mkdir()
                (target/"shape_chamfer.json").write_text(json.dumps(metrics()))
                (out/"shape-scorer-provenance.json").write_text(json.dumps({
                    **provenance, "scorer_status": "UPSTREAM_SHAPE_CHAMFER_EXECUTED"}))
            with patch("geometry_harness.evaluation.counterfactual_shape._preflight",
                       return_value=(historical, provenance, old, originals, derived)), patch(
                "geometry_harness.evaluation.counterfactual_shape._precheck_scorer"), patch(
                "geometry_harness.evaluation.counterfactual_shape.blender_binary") as blender, patch(
                "geometry_harness.evaluation.counterfactual_shape._safe_run") as export, patch(
                "geometry_harness.evaluation.counterfactual_shape.score", side_effect=fake_score):
                result = run(root, root, root, out, upstream=root, refs=root, resume=True)
                blender.assert_not_called()
                export.assert_not_called()
            self.assertEqual(result["shape_status"], "SCORED_PINNED_COUNTERFACTUAL")
            self.assertEqual(result["n_scored"], 5)
            # Neither an existing result nor a tampered staged file can be resumed.
            with self.assertRaisesRegex(ShapeGateError, "unscored"):
                _validate_resumable_stage(out, historical, originals, derived)
            (out/"counterfactual-shape-results.json").unlink()
            (out/"shape-scorer-provenance.json").unlink()
            (base/"_metrics"/"shape_chamfer.json").unlink()
            (base/"_metrics").rmdir()
            tampered = base / TASK_IDS[0] / "glb" / f"{TASK_IDS[0]}.glb"
            tampered.write_bytes(b"glTFnot-the-original")
            with self.assertRaisesRegex(ShapeGateError, "SHA/size mismatch"):
                _validate_resumable_stage(out, historical, originals, derived)

    def test_readonly_diagnostics_accepts_descriptive_unpaired_when_frozen(self):
        from types import SimpleNamespace
        import hashlib
        from geometry_harness.evaluation.counterfactual_shape import diagnose_existing
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            upstream, refs, out = (root/p for p in ("upstream", "refs", "out"))
            (upstream/"metrics").mkdir(parents=True)
            refs.mkdir()
            out.mkdir()
            script = b"# pinned third party script\\n"
            (upstream/"metrics"/"shape_chamfer.py").write_bytes(script)
            (refs/"reference-provenance.json").write_text("{}")
            previous_refs = []
            ref_manifest = []
            for task in EXPECTED_IDS:
                mesh = refs/task/"glb"/f"{task}.glb"
                mesh.parent.mkdir(parents=True)
                mesh.write_bytes(b"glTF" + task.encode())
                sha = hashlib.sha256(mesh.read_bytes()).hexdigest()
                previous_refs.append({"task_id": task, "sha256": sha})
                ref_manifest.append({"task_id": task, "reference_glb_sha256": sha,
                                     "reference_glb_bytes": mesh.stat().st_size})
            (refs/"reference-provenance.json").write_text(json.dumps({"refs":ref_manifest}))
            baseline = metrics()
            for row in baseline["per_instance"]:
                if row["instance"] not in ORIGINAL_VALID:
                    row.update(status="NO_GEN_GLB", cd=None, cd_yawmin=None)
            baseline["n_ok"] = 2
            new = metrics(changed=True)
            (out/"results"/"text_to_3D"/"gpt-6-luna"/"_metrics").mkdir(parents=True)
            target = out/"results"/"text_to_3D"/"gpt-6-luna"/"_metrics"/"shape_chamfer.json"
            target.write_text(json.dumps(new))
            provenance = {"upstream_commit":UPSTREAM_COMMIT,
                          "dataset_revision":"frozen-dataset",
                          "upstream_shape_scorer_sha256":hashlib.sha256(script).hexdigest(),
                          "reference_glb_sha256":previous_refs}
            (out/"shape-scorer-provenance.json").write_text(json.dumps(provenance))
            def fake_git(cmd, **kwargs):
                if "rev-parse" in cmd:
                    return SimpleNamespace(stdout=UPSTREAM_COMMIT)
                return SimpleNamespace(stdout=script)
            original = {"dataset_revision":"frozen-dataset"}
            with patch("geometry_harness.evaluation.counterfactual_shape._preflight",
                       return_value=(original,provenance,baseline,{},{})), patch(
                       "geometry_harness.evaluation.counterfactual_shape._validate_resumable_stage") as stage, patch(
                       "subprocess.run", side_effect=fake_git):
                diagnostic = diagnose_existing(root, root, root, out, upstream, refs)
            self.assertEqual(diagnostic["shape_status"],"DESCRIPTIVE_5_SCENES_NOT_PAIRED")
            self.assertEqual(diagnostic["n_scored"],5)
            self.assertTrue(diagnostic["frozen_references_match"])
            self.assertTrue(diagnostic["frozen_scorer_matches"])
            self.assertFalse(diagnostic["original_pair_exact_scores_reproduce"])
            self.assertEqual(len(diagnostic["per_instance"]),6)
            stage.assert_called_once()
            self.assertTrue(stage.call_args.kwargs["allow_scored_readonly"])

    def test_diagnosis_exposes_no_scored_claim_with_bad_references(self):
        from geometry_harness.evaluation.counterfactual_shape import diagnose_existing
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"metrics").mkdir()
            (root/"metrics"/"shape_chamfer.py").write_text("# trusted script")
            (root/"reference-provenance.json").write_text("{}")
            with patch("geometry_harness.evaluation.counterfactual_shape._preflight") as original:
                # A failed private audit is never bypassed to show a metric.
                original.side_effect=ValueError("missing original")
                with self.assertRaisesRegex(ValueError,"missing original"):
                    diagnose_existing(root,root,root,root,root,root)

if __name__ == "__main__":
    unittest.main()
