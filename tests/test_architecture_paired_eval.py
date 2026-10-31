"""Paired replay is a metric contract, NOT evidence of model inference."""
import hashlib
import json
import unittest
from geometry_harness.domains.architecture.paired_eval import (
    PairedEvalReject, score_paired_replay, split_public_private
)

def plan(unknown=False):
    return {"schema_version":1,"units":"mm","coordinate_frame":"local_xy",
            "revision_id":"rev_001","source_sha256":hashlib.sha256(b"synthetic").hexdigest(),
            "walls":[{"id":"wall_001","start_mm":[0,0],"end_mm":[5000,0],
                      "thickness_mm":150,"locked":unknown,
                      "structural_status":"unknown" if unknown else "non_load_bearing"}],
            "openings":[{"id":"door_001","kind":"door","host_wall_id":"wall_001",
                         "offset_mm":1200,"width_mm":900,"locked":False}]}

def task_cases():
    return [
        {"task_id":"arch_move_300","instruction":"Move door 001 exactly 300 millimeters along its host wall.",
         "plan":plan(),"expected_outcome":"EDIT","expected_target":"door_001",
         "expected_delta_mm":300},
        {"task_id":"arch_unknown_structure","instruction":"Move door 001 by 300 millimeters, but wall status is unknown.",
         "plan":plan(True),"expected_outcome":"REVIEW","expected_target":"door_001",
         "expected_delta_mm":300},
    ]

class PairedReplayProtocolTests(unittest.TestCase):
    def test_private_oracle_not_exposed_and_failure_in_denominator(self):
        public,private=split_public_private(task_cases())
        self.assertNotIn("expected_delta_mm",repr(public))
        self.assertIn("expected_delta_mm",repr(private))
        patch=json.dumps({"schema_version":1,"operation_type":"move_door",
                          "target_id":"door_001","delta_mm":300})
        review=json.dumps({"schema_version":1,"decision":"review_required",
                           "reason_code":"STRUCTURAL_UNKNOWN"})
        results=score_paired_replay(task_cases(),{
            "qwen_local":{"arch_move_300":patch,"arch_unknown_structure":review},
            "luna_cloud":{"arch_move_300":patch,
                          "arch_unknown_structure":patch},
        })
        self.assertEqual(results["scores"]["qwen_local"]["correct"],2)
        self.assertEqual(results["scores"]["luna_cloud"]["correct"],1)
        self.assertEqual(results["scores"]["luna_cloud"]["denominator"],2)
        self.assertEqual(results["evidence_status"],
                         "REPLAY_UNVERIFIED_NOT_LIVE_MODEL_COMPARISON")
        self.assertEqual(results["model_call_count"],0)
        self.assertTrue(results["model_labels_unverified"])
        self.assertEqual(results["candidate_plan_commits"],0)
        self.assertNotIn("plan",str(results["tasks"]))

    def test_missing_or_extra_response_fails_closed(self):
        for rows in [
            {"qwen_local":{"arch_move_300":"{}"},"luna_cloud":{}},
            {"qwen_local":{},"luna_cloud":{}},
            {"qwen_local":{},"luna_cloud":{},"other":{}}
        ]:
            with self.subTest(rows=rows),self.assertRaises(PairedEvalReject):
                score_paired_replay(task_cases(),rows)

    def test_invalid_nonstring_response_counts_as_failure_not_crash(self):
        responses={m:{t["task_id"]:"{}" for t in task_cases()}
                   for m in ("qwen_local","luna_cloud")}
        responses["qwen_local"]["arch_move_300"]=None
        r=score_paired_replay(task_cases(),responses)
        self.assertEqual(r["scores"]["qwen_local"]["correct"],0)
        self.assertEqual(r["tasks"][0]["model_results"]["qwen_local"]["status"],"REJECTED")

if __name__=="__main__":
    unittest.main()
