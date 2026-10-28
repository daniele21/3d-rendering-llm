"""Real Blender smoke for the restricted G1 path; zero provider calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from geometry_harness.g1 import create_g1, ShowcaseError

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "g1_safe_table.py"


class SafeG1BlenderTests(unittest.TestCase):
    def test_real_trusted_blender_native_scene_no_model(self):
        root = Path(os.environ.get("GEOMETRY_G1_FIXTURE_DIR",
                                   "ci-artifacts/showcase/g1-fixture")).resolve()
        self.assertFalse(root.exists(), "G1 fixture bundle must be fresh for reliable evidence")
        result = create_g1(root, fixture_source=FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["evidence_type"], "trusted_fixture_safe_literal_bpy_to_blender")
        self.assertEqual(len(json.loads((root / "artifacts" / "geometry.json").read_text())["mesh_objects"]), 5)
        self.assertTrue((root / "artifacts" / "scene.blend").read_bytes().startswith(b"BLENDER"))
        self.assertGreater((root / "artifacts" / "preview.png").stat().st_size, 100)
        self.assertTrue((root / "index.html").is_file())
        trace = json.loads((root / "performance-summary.json").read_text())
        self.assertEqual(trace["status"], "COMPLETE")
        self.assertIn("blender.build", {x["name"] for x in trace["spans"]})
        self.assertIn("scene.reopen", {x["name"] for x in trace["spans"]})
        self.assertEqual(trace["unsettled_span_count"], 0)
        self.assertIn("trace.jsonl", {a["path"] for a in result["artifacts"]})

    def test_unsafe_model_code_fails_closed_without_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "invalid"
            with self.assertRaisesRegex(ShowcaseError, "G1 run failed"):
                create_g1(target, fixture_source="import os\nos.system('touch /tmp/unsafe_g1_marker')")
            self.assertFalse((target / "artifacts" / "scene.blend").exists())
            manifest = json.loads((target / "showcase-manifest.json").read_text())
            self.assertEqual(manifest["status"], "FAIL")
            trace = json.loads((target / "performance-summary.json").read_text())
            self.assertEqual(trace["status"], "FAIL")
            self.assertEqual(manifest["evidence_type"], "trusted_fixture_safe_literal_bpy_to_blender")
            self.assertFalse(Path("/tmp/unsafe_g1_marker").exists())


if __name__ == "__main__":
    unittest.main()
