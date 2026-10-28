"""Six-task audit, independent cost reconciliation and leak controls. No AI."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from geometry_harness.evaluation.benchmark_evidence import audit, gallery, EvidenceError, EXPECTED_IDS, EXPECTED_DATASET


def _png():
    # Only a PNG-shaped header for the *evidence parser* contract test,
    # not a real Blender rendering. Real E2E evidence is a separate CI gate.
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 3, 4) + b"\x08\x02\x00\x00\x00" + b"fake-crc"


def make(root):
    def store(rel, data):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else (json.dumps(data)+"\n").encode())
    report = {"dataset_revision": EXPECTED_DATASET, "model":"gpt-6-luna",
              "source_sha":"sha", "smoke_ids":list(EXPECTED_IDS),
              "scene_passes":2, "model_estimated_usd":"0.000006",
              "status":"INCOMPLETE", "task_results":[]}
    cost_events = []
    for i, task in enumerate(EXPECTED_IDS):
        state = "PASS" if i < 2 else "UNKNOWN"
        record = {"task_id":task, "native_scene":state,"provider_outcome":"COMPLETED",
                  "usd_estimate":"0.000001","error_class":None}
        report["task_results"].append(record)
        store(f"tasks/{task}/result.json",record)
        if i < 2:
            store(f"tasks/{task}/scene.blend",b"BLENDERfake")
            store(f"tasks/{task}/preview.png",_png())
            store(f"tasks/{task}/geometry.json",{
                "passed":True,"mesh_objects":[{"name":"cube","dimensions":[1,1,1]}]})
        cost_events.append({"event":"started","call_id":str(i),
                            "model_requested":"gpt-6-luna","stage":"test"})
        cost_events.append({"event":"settled","call_id":str(i),
                            "model_returned":"gpt-6-luna",
                            "pricing":{"status":"PRICED","estimated_usd":"0.000001",
                                       "tokens":{"input_total":100,"input_uncached":100,
                                                 "input_cache_read":0,
                                                 "input_cache_write_30m":0,
                                                 "input_cache_write_12h":0,
                                                 "output_total":10,
                                                 "output_reasoning_subset":0}}})
    store("costs/events.jsonl",("\n".join(json.dumps(x) for x in cost_events)+"\n").encode())
    store("cost-summary.json",{"grand_total_status":"COMPLETE","recorded_calls":6,
                               "priced_subtotal_usd":"0.000006"})
    store("benchmark.json",report)
    files=[]
    for p in root.rglob("*"):
        if p.is_file():
            files.append({"path":str(p.relative_to(root)),"bytes":p.stat().st_size,
                          "sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    store("bundle-manifest.json",{"model":"gpt-6-luna","source_sha":"sha",
                                 "dataset_revision":EXPECTED_DATASET,"files":files})


class BenchmarkEvidenceTests(unittest.TestCase):
    def test_true_denominator_with_original_failed_ci(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            make(root)
            a=audit(root)
            self.assertEqual(a["original_run_status"],"INCOMPLETE")
            self.assertEqual((a["native_pass"],a["native_fail"],a["native_unknown"]),(2,0,4))
            self.assertEqual(a["native_pass_rate"],2/6)
            self.assertEqual(a["cost_status"],"COMPLETE")
            self.assertIsNone(a["shape_score"])
            self.assertIsNone(a["visual_score"])
            self.assertIn("UNKNOWN",gallery(a))
            self.assertEqual(a["model_estimated_usd"],"0.000006")

    def test_modified_cost_or_image_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            make(root)
            img=root/"tasks"/EXPECTED_IDS[0]/"preview.png"
            img.write_bytes(img.read_bytes()+b"malicious-change")
            with self.assertRaisesRegex(EvidenceError,"SHA"):
                audit(root)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            make(root)
            cost=root/"cost-summary.json"
            cost.write_text('{"grand_total_status":"COMPLETE","recorded_calls":6,"priced_subtotal_usd":"0"}')
            with self.assertRaises(EvidenceError):
                audit(root)

    def test_missing_result_and_reference_leak_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            make(root)
            (root/"tasks"/EXPECTED_IDS[1]/"result.json").unlink()
            with self.assertRaises(EvidenceError):
                audit(root)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            make(root)
            manifest=json.loads((root/"bundle-manifest.json").read_text())
            manifest["files"].append({"path":"reference/factory.py","bytes":12,"sha256":"0"*64})
            (root/"bundle-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(EvidenceError,"Reference|Python"):
                audit(root)


if __name__ == "__main__":
    unittest.main()
