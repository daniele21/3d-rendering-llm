"""Real Blender proof for bounded cylinder/sphere scene; no remote model call."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from geometry_harness.cli import blender_binary, ShowcaseError
from geometry_harness.g1 import create_g1, _safe_run, BUILDER, INSPECT
from geometry_harness.strategies.bpy_subset import compile_bpy_subset


CYL_TABLE = """import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))
obj = bpy.context.object
obj.name = "tabletop"
obj.dimensions = (2,1,.08)
"""
for i, (x, y) in enumerate([(-.8,-.3),(-.8,.3),(.8,-.3),(.8,.3)], 1):
    CYL_TABLE += f"""
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=.04, depth=.96, location=({x},{y},.48))
obj = bpy.context.object
obj.name = "leg_{i}"
"""


class GeometryPrimitiveBlenderTests(unittest.TestCase):
    def test_mixed_cube_and_four_cylinder_parts(self):
        output = Path(os.environ.get("GEOMETRY_G1_CYLINDER_DIR",
                                     "ci-artifacts/showcase/g1-cylinder-fixture")).resolve()
        self.assertFalse(output.exists(), "Owned fixture directory must be fresh")
        manifest = create_g1(output, fixture_source=CYL_TABLE)
        self.assertEqual(manifest["status"], "PASS")
        self.assertEqual(manifest["model_calls"], 0)
        geometry = json.loads((output/"artifacts"/"geometry.json").read_text())
        self.assertEqual(len(geometry["mesh_objects"]), 5)
        self.assertTrue((output/"artifacts"/"scene.blend").read_bytes().startswith(b"BLENDER"))
        self.assertGreater((output/"artifacts"/"preview.png").stat().st_size, 100)

    def test_real_sphere_blender_and_independent_reopen(self):
        binary = blender_binary()
        if not binary:
            self.skipTest("Blender is required for real native test")
        raw = """import bpy
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=.4, location=(0,0,.4))
obj = bpy.context.object
obj.name = "ball"
"""
        spec = compile_bpy_subset(raw)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            art = root/"artifacts"
            art.mkdir()
            spec_file = art/"scene-spec.json"
            spec_file.write_text(json.dumps(spec))
            _safe_run([binary, "-b", "--factory-startup", "--python-exit-code", "14",
                       "--python", str(BUILDER), "--", "--spec", str(spec_file),
                       "--out", str(art)], root/"build.txt")
            _safe_run([binary, "-b", str(art/"scene.blend"), "--python-exit-code", "14",
                       "--python", str(INSPECT), "--", "--spec", str(spec_file),
                       "--output", str(art/"geometry.json")], root/"inspect.txt")
            measured = json.loads((art/"geometry.json").read_text())
            self.assertTrue(measured["passed"])
            self.assertEqual(len(measured["mesh_objects"]), 1)
            self.assertEqual(measured["mesh_objects"][0]["name"], "ball")


if __name__ == "__main__":
    unittest.main()
