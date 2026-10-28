"""Real native safe-builder repair/rollback: 0 provider calls."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from geometry_harness.cli import blender_binary
from geometry_harness.g1 import BUILDER, INSPECT, _safe_run, table_validation_contract
from geometry_harness.repair.scoped import execute
from geometry_harness.strategies.bpy_subset import compile_bpy_subset
from geometry_harness.validation.issues import validate


class ScopedNativeBlenderTests(unittest.TestCase):
    def test_disconnected_leg_is_fixed_and_bad_candidate_rolled_back(self):
        out = Path(os.environ.get("GEOMETRY_REPAIR_FIXTURE_DIR",
                                  "ci-artifacts/showcase/repair-fixture")).resolve()
        self.assertFalse(out.exists(), "Evidence directory must be new")
        out.mkdir(parents=True)
        binary = blender_binary()
        self.assertIsNotNone(binary, "Real Blender mandatory")
        raw = """import bpy
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,1))
obj=bpy.context.object
obj.name="tabletop"
obj.dimensions=(2,1,.08)
"""
        for i,(x,y) in enumerate(((-.8,-.3),(-.8,.3),(.8,-.3),(.8,.3)),1):
            z=.60 if i == 1 else .48
            raw += f"""
bpy.ops.mesh.primitive_cube_add(size=1,location=({x},{y},{z}))
obj=bpy.context.object
obj.name="leg_{i}"
obj.dimensions=(.08,.08,.96)
"""
        original = out/"original"
        original.mkdir()
        spec = original/"scene-spec.json"
        spec.write_text(json.dumps(compile_bpy_subset(raw)), encoding="utf8")
        _safe_run([binary,"-b","--factory-startup","--python-exit-code","14",
                   "--python",str(BUILDER),"--","--spec",str(spec),
                   "--out",str(original)],out/"source-build.txt")
        blend=original/"scene.blend"
        before_hash=hashlib.sha256(blend.read_bytes()).hexdigest()
        base=json.loads(spec.read_text())
        leg=next(p for p in base["objects"] if p["name"]=="leg_1")
        self.assertEqual(leg["location"][2],.6)
        command={"schema_version":1,"operation_id":"repair_one_leg",
                 "operation_type":"set_location","target_id":"leg_1",
                 "scene_spec_sha256":hashlib.sha256(spec.read_bytes()).hexdigest(),
                 "scene_blend_sha256":before_hash,
                 "expected_location_m":leg["location"],
                 "new_location_m":[leg["location"][0],leg["location"][1],.48]}
        approved=execute(blend,spec,command,table_validation_contract(),out/"accepted")
        self.assertEqual(approved["status"],"ACCEPTED")
        self.assertEqual(approved["before_status"],"FAIL")
        self.assertEqual(approved["after_status"],"PASS")
        self.assertEqual(approved["model_calls"],0)
        self.assertEqual(hashlib.sha256(blend.read_bytes()).hexdigest(),before_hash)
        self.assertTrue((out/"accepted"/"accepted.blend").read_bytes().startswith(b"BLENDER"))
        self.assertEqual(hashlib.sha256((out/"accepted"/"rollback.blend").read_bytes()).hexdigest(),before_hash)
        observed=json.loads((out/"accepted"/"candidate-geometry.json").read_text())
        source_obs=json.loads((out/"accepted"/"original-geometry.json").read_text())
        by_name={x["name"]:x for x in observed["mesh_objects"]}
        source_by={x["name"]:x for x in source_obs["mesh_objects"]}
        for name in source_by:
            if name!="leg_1":
                self.assertEqual(source_by[name],by_name[name])
        self.assertEqual(validate(observed,table_validation_contract())["status"],"PASS")
        bad={**command,"operation_id":"bad_leg_fix",
             "new_location_m":[leg["location"][0],leg["location"][1],.70]}
        rollback=execute(blend,spec,bad,table_validation_contract(),out/"rejected")
        self.assertEqual(rollback["status"],"ROLLED_BACK")
        self.assertFalse((out/"rejected"/"accepted.blend").exists())
        self.assertEqual(hashlib.sha256((out/"rejected"/"rollback.blend").read_bytes()).hexdigest(),before_hash)
        self.assertEqual(hashlib.sha256(blend.read_bytes()).hexdigest(),before_hash)


if __name__=="__main__":
    unittest.main()
