"""Real Blender validation images and geometry checks; 0 paid model calls."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from geometry_harness.cli import blender_binary
from geometry_harness.g1 import _safe_run, create_g1
from geometry_harness.validation.issues import validate
from test_validation_issues import contract

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "g1_safe_table.py"
SCRIPT = Path(__file__).resolve().parents[2] / "src" / "geometry_harness" / "blender" / "render_validation_views.py"


class RealViewsTests(unittest.TestCase):
    def test_four_independent_views_and_scene_unchanged(self):
        out = Path(os.environ.get("GEOMETRY_VAL_FIXTURE_DIR",
                                  "ci-artifacts/showcase/val-fixture")).resolve()
        self.assertFalse(out.exists(), "Each native evidence bundle needs a new folder")
        root = create_g1(out, fixture_source=FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(root["status"], "PASS")
        scene = out / "artifacts" / "scene.blend"
        before = hashlib.sha256(scene.read_bytes()).hexdigest()
        measured = json.loads((out/"artifacts"/"geometry.json").read_text())
        report = validate(measured, contract())
        self.assertEqual(report["status"], "PASS")
        (out/"geometry-issues.json").write_text(json.dumps(report, indent=2)+"\n")
        binary = blender_binary()
        self.assertIsNotNone(binary, "Real Blender mandatory for this test")
        _safe_run([binary, "-b", str(scene), "--python-exit-code", "14",
                   "--python", str(SCRIPT), "--", "--out", str(out/"views")],
                  out/"views-run.txt", limit=120)
        manifest = json.loads((out/"views"/"views-manifest.json").read_text())
        self.assertEqual({x["view"] for x in manifest["views"]},
                         {"front","side","top","isometric"})
        self.assertEqual(manifest["quality_judgement"], "UNKNOWN_NO_VISUAL_JUDGE")
        self.assertEqual(before, hashlib.sha256(scene.read_bytes()).hexdigest())
        for x in manifest["views"]:
            path = out/"views"/x["path"]
            self.assertGreater(path.stat().st_size, 100)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), x["sha256"])


if __name__ == "__main__":
    unittest.main()
