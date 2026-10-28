"""Historical GCS reader remains operator-only; never edits IAM or replays API."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.evaluation.historical_luna import operate,SOURCE_GCS


class HistoricLunaTests(unittest.TestCase):
    def test_read_only_local_evidence_no_network_and_unknown_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            local=root/"trusted-source"
            (local/"tasks").mkdir(parents=True)
            (local/"tasks"/"preview.png").write_bytes(b"fake")
            audit_result={
                "original_run_status":"INCOMPLETE",
                "audit_status":"EVIDENCE_VERIFIED_NOT_UPSTREAM_SCORED",
                "native_pass":2,"task_count":6,
                "model_estimated_usd":"0.004875300",
                "tasks":[{"preview_path":"tasks/preview.png"}],
            }
            with patch("geometry_harness.evaluation.historical_luna.audit",
                       return_value=audit_result),patch(
                "geometry_harness.evaluation.historical_luna.gallery",
                return_value="<html>ORIGINAL CI FAILED</html>"),patch(
                "geometry_harness.evaluation.historical_luna.subprocess.run") as remote:
                result=operate(root/"reviewed",source_local=local)
                remote.assert_not_called()
            self.assertEqual(result["original_run_status"],"INCOMPLETE")
            self.assertEqual(result["quality_score"],"UNKNOWN_UPSTREAM_NOT_RUN")
            self.assertEqual(result["native_pass"],2)
            self.assertEqual((root/"reviewed"/"review"/"tasks"/"preview.png").read_bytes(),b"fake")
            with self.assertRaises(ValueError):
                operate(root/"reviewed",source_local=local)

    def test_immutable_original_gcs_locator_and_no_provisioning(self):
        self.assertIn("40683850012-attempt-1/g1-benchmark",SOURCE_GCS)
        self.assertNotIn("public",SOURCE_GCS)
        with tempfile.TemporaryDirectory() as tmp,patch(
            "geometry_harness.evaluation.historical_luna.shutil.which",
            return_value=None),patch(
            "geometry_harness.evaluation.historical_luna.subprocess.run") as remote:
            with self.assertRaisesRegex(RuntimeError,"gcloud CLI missing"):
                operate(Path(tmp)/"out")
            remote.assert_not_called()


if __name__=="__main__":
    unittest.main()
