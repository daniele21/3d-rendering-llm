"""No-cost guard tests for pinned, reference-isolated scorer adapter."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from geometry_harness.evaluation.upstream_shape_adapter import score, ShapeGateError, UPSTREAM_COMMIT


class ShapeAdapterTests(unittest.TestCase):
    def test_scoring_blocks_wrong_commit_without_any_metric(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            out=base/"out"
            out.mkdir()
            (out/"scorer-staging.json").write_text(json.dumps({
                "upstream_commit":UPSTREAM_COMMIT,
                "dataset_revision":"b70b4ee54b93fab76596da5809f3e71c617fa5c2",
                "original_run_status":"INCOMPLETE"
            }))
            upstream=base/"upstream"
            (upstream/"metrics").mkdir(parents=True)
            (upstream/"metrics"/"shape_chamfer.py").write_text("print('untrusted code')\n")
            refs=base/"ref"
            refs.mkdir()
            with patch("geometry_harness.evaluation.upstream_shape_adapter.subprocess.run",
                       return_value=Mock(stdout="f"*40)) as run:
                with self.assertRaisesRegex(ShapeGateError,"pinned commit"):
                    score(out,upstream,refs)
                self.assertEqual(run.call_count,1)
                self.assertFalse((out/"shape-scorer-provenance.json").exists())

    def test_scoring_refuses_missing_reference_mesh_and_no_implicit_export(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            out=base/"out"
            out.mkdir()
            (out/"scorer-staging.json").write_text(json.dumps({"upstream_commit":UPSTREAM_COMMIT}))
            upstream=base/"upstream"
            (upstream/"metrics").mkdir(parents=True)
            (upstream/"metrics"/"shape_chamfer.py").write_text("# pinned code location")
            refs=base/"refs"
            refs.mkdir()
            with patch("geometry_harness.evaluation.upstream_shape_adapter.subprocess.run",
                       return_value=Mock(stdout=UPSTREAM_COMMIT)) as invoke:
                with self.assertRaisesRegex(ShapeGateError,"reference GLBs"):
                    score(out,upstream,refs)
                self.assertEqual(invoke.call_count,1)
                self.assertFalse((out/"shape-scorer-provenance.json").exists())


if __name__=="__main__":
    unittest.main()
