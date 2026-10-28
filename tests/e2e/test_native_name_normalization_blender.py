"""Real Blender verification that normalized aliases and ordinal IDs survive reopen."""
import json
from pathlib import Path
import tempfile
import unittest

from geometry_harness.cli import blender_binary, png_dimensions
from geometry_harness.g1 import BUILDER, INSPECT, _safe_run
from geometry_harness.strategies.bpy_subset import compile_bpy_subset


class NativeNameNormalizerE2E(unittest.TestCase):
    def test_collision_preserves_original_name_and_persists_independent_ids(self):
        executable = blender_binary()
        if not executable:
            self.skipTest("Blender required for native E2E")
        raw = """import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))
obj=bpy.context.object
obj.name="Glass pane"
obj.dimensions=(1,1,1)
bpy.ops.mesh.primitive_cube_add(size=1, location=(2,0,1))
obj=bpy.context.object
obj.name="Glass_pane"
obj.dimensions=(1,1,1)
"""
        spec = compile_bpy_subset(raw, normalize_names=True)
        self.assertEqual([p["name"] for p in spec["objects"]], ["Glass_pane__2", "Glass_pane"])
        self.assertEqual(spec["name_normalization"]["changes"], 1)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/"spec.json").write_text(json.dumps(spec))
            native = root / "native"
            native.mkdir()
            _safe_run([executable, "-b", "--factory-startup", "--disable-autoexec",
                       "--python-exit-code", "14", "--python", str(BUILDER),
                       "--", "--spec", str(root/"spec.json"), "--out", str(native)],
                      root/"build.log")
            self.assertEqual((native/"scene.blend").read_bytes()[:7], b"BLENDER")
            _safe_run([executable, "-b", str(native/"scene.blend"), "--disable-autoexec",
                       "--python-exit-code", "14", "--python", str(INSPECT),
                       "--", "--spec", str(root/"spec.json"), "--output", str(root/"reopened.json")],
                      root/"inspect.log")
            evidence = json.loads((root/"reopened.json").read_text())
            self.assertTrue(evidence["passed"])
            self.assertEqual({p["geometry_id"] for p in evidence["mesh_objects"]},
                             {"mesh_001", "mesh_002"})
            self.assertEqual({p["name"] for p in evidence["mesh_objects"]},
                             {"Glass_pane", "Glass_pane__2"})
            self.assertEqual(png_dimensions(native/"preview.png"), (800, 600))


if __name__ == "__main__":
    unittest.main()
