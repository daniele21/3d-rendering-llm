"""No-cost typed edits; real Blender integration is in tests/e2e."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from geometry_harness.repair.scoped import preflight, RepairError


def spec():
    return {"parser":"safe_literal_bpy_cube_v1","objects":[
        {"name":"tabletop","kind":"cube","location":[0,0,1],"dimensions":[2,1,.08]},
        {"name":"leg_1","kind":"cube","location":[-.8,-.3,.60],"dimensions":[.08,.08,.96]},
        {"name":"leg_2","kind":"cube","location":[.8,-.3,.48],"dimensions":[.08,.08,.96]}]}


def patch():
    return {"schema_version":1,"operation_id":"move_leg_1",
            "operation_type":"set_location","target_id":"leg_1",
            "scene_spec_sha256":"a"*64, "scene_blend_sha256":"b"*64,
            "expected_location_m":[-.8,-.3,.6],
            "new_location_m":[-.8,-.3,.48]}


class TypedScopedPatchTests(unittest.TestCase):
    def test_changed_only_named_target(self):
        start=spec()
        result=preflight(start,patch(),"a"*64,"b"*64)
        self.assertEqual(result["objects"][1]["location"],[-.8,-.3,.48])
        self.assertEqual(start["objects"][1]["location"],[-.8,-.3,.60])
        self.assertEqual(result["objects"][0],start["objects"][0])
        self.assertEqual(result["objects"][2],start["objects"][2])

    def test_stale_scope_guards(self):
        variants=[]
        for k,v in (("scene_blend_sha256","c"*64),
                    ("target_id","unknown"),
                    ("expected_location_m",[0,0,0]),
                    ("operation_type","exec_python"),
                    ("new_location_m",[0,0,25]),
                    ("new_location_m",[0,0,float("nan")])):
            x=patch()
            x[k]=v
            variants.append(x)
        for changed in variants:
            with self.subTest(changed=changed),self.assertRaises(RepairError):
                preflight(spec(),changed,"a"*64,"b"*64)
        x=patch()
        x["python"]="__import__('os').system('echo unsafe')"
        with self.assertRaises(RepairError):
            preflight(spec(),x,"a"*64,"b"*64)
        x=patch()
        x["new_location_m"]=x["expected_location_m"]
        with self.assertRaises(RepairError):
            preflight(spec(),x,"a"*64,"b"*64)


if __name__=="__main__":
    unittest.main()
