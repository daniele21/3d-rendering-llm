"""Real Mac Blender DXF-to-mesh pipeline. No AI calls, no external files."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from geometry_harness.cli import blender_binary
from geometry_harness.dxf_safe import compile_dxf
from geometry_harness.g1 import BUILDER, INSPECT, _safe_run
from geometry_harness.validation.issues import validate

FIXTURE=Path(__file__).resolve().parents[1]/"fixtures"/"arch01_room_mm.dxf"


class RealDXFWallsTests(unittest.TestCase):
    def test_four_dxf_mm_walls_are_native_reopenable_blender_objects(self):
        root=Path(os.environ.get("GEOMETRY_ARCH_FIXTURE_DIR",
                                  "ci-artifacts/showcase/arch01-fixture")).resolve()
        self.assertFalse(root.exists())
        root.mkdir(parents=True)
        binary=blender_binary()
        self.assertIsNotNone(binary)
        spec=compile_dxf(FIXTURE.read_text(encoding="utf8"))
        spec_file=root/"walls-spec.json"
        spec_file.write_text(json.dumps(spec,indent=2)+"\n")
        wall_dir=root/"native"
        _safe_run([binary,"-b","--factory-startup","--disable-autoexec",
                   "--python-exit-code","14","--python",str(BUILDER),
                   "--","--spec",str(spec_file),"--out",str(wall_dir)],
                  root/"build.txt",limit=90)
        scene=wall_dir/"scene.blend"
        self.assertTrue(scene.is_file())
        digest=hashlib.sha256(scene.read_bytes()).hexdigest()
        _safe_run([binary,"-b",str(scene),"--disable-autoexec",
                   "--python-exit-code","14","--python",str(INSPECT),
                   "--","--spec",str(spec_file),
                   "--output",str(root/"reopened.json")],
                  root/"reopen.txt",limit=90)
        measured=json.loads((root/"reopened.json").read_text())
        self.assertTrue(measured["passed"])
        self.assertEqual(len(measured["mesh_objects"]),4)
        contract={"schema_version":1,"task_id":"synthetic_rectangular_room",
                  "units":"m","requirements":[
                      {"id":f"wall_{i:02d}_size","type":"dimensions",
                       "object_id":f"wall_{i:02d}",
                       "expected_dimensions_m":p["dimensions"],
                       "tolerance_m":.005} for i,p in enumerate(spec["objects"],1)]}
        checks=validate(measured,contract)
        self.assertEqual(checks["status"],"PASS")
        (root/"validation.json").write_text(json.dumps(checks,indent=2)+"\n")
        self.assertTrue((wall_dir/"preview.png").is_file())
        self.assertEqual(digest,hashlib.sha256(scene.read_bytes()).hexdigest())
        self.assertEqual(spec["source_units_code"],4)


if __name__=="__main__":
    unittest.main()
