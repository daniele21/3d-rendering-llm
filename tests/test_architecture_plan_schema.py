"""Pure offline validation of bounded, source-linked architectural 2D state."""
import copy
import unittest

from geometry_harness.domains.architecture.schema import (
    PlanReject, plan_sha256, plan_summary, validate_plan
)


def example_plan():
    return {
        "schema_version": 1,
        "units": "mm", "coordinate_frame": "local_xy",
        "revision_id": "rev_001", "source_sha256": "a" * 64,
        "walls": [
            {"id":"wall_001","start_mm":[0,0],"end_mm":[5000,0],
             "thickness_mm":150,"locked":True,"structural_status":"unknown"},
            {"id":"wall_002","start_mm":[5000,0],"end_mm":[5000,4000],
             "thickness_mm":150,"locked":False,"structural_status":"non_load_bearing"},
        ],
        "openings": [
            {"id":"door_001","kind":"door","host_wall_id":"wall_001",
             "offset_mm":1200,"width_mm":900,"locked":False},
            {"id":"window_001","kind":"window","host_wall_id":"wall_002",
             "offset_mm":1000,"width_mm":1200,"locked":True}
        ],
    }


class PlanSchemaTests(unittest.TestCase):
    def test_nominal_scene_and_stable_hash_and_provenance(self):
        original = example_plan()
        before=copy.deepcopy(original)
        result=validate_plan(original)
        self.assertEqual(original, before)
        self.assertEqual(result["walls"][0]["id"],"wall_001")
        self.assertEqual(plan_sha256(result), plan_sha256(original))
        report=plan_summary(original)
        self.assertEqual(report["opening_count"], 2)
        self.assertEqual(report["unknown_structural_count"], 1)
        self.assertEqual(report["room_topology"],"UNKNOWN_NOT_MODELED")
        changed=copy.deepcopy(original)
        changed["openings"][0]["offset_mm"]+=300
        self.assertNotEqual(plan_sha256(original),plan_sha256(changed))

    def test_rejects_nonmm_and_fabricated_provenance(self):
        for key,bad in (
            ("units","m"), ("units",None),
            ("coordinate_frame","EPSG:4326"),
            ("source_sha256","missing"), ("source_sha256","Z"*64),
            ("schema_version", True), ("schema_version",2),
            ("revision_id","../oops")):
            with self.subTest(key=key,bad=bad):
                x=example_plan(); x[key]=bad
                with self.assertRaises(PlanReject):
                    validate_plan(x)

    def test_rejects_unsafe_numeric_id_extra_fields(self):
        scenarios=[
            ("walls",0,"start_mm",[True,0]),
            ("walls",0,"start_mm",[1.0,0]),
            ("walls",0,"end_mm",[0,0]),
            ("walls",0,"thickness_mm",True),
            ("walls",0,"thickness_mm",150.25),
            ("walls",0,"locked",1),
            ("walls",0,"structural_status","maybe"),
            ("openings",0,"width_mm",-100),
            ("openings",0,"width_mm",900.0),
            ("openings",0,"offset_mm",5000),
            ("openings",0,"host_wall_id","not_present"),
            ("openings",0,"id","window/str"),
            ("openings",0,"kind","stair"),
            ("openings",0,"locked","yes"),
        ]
        for typ,n,key,val in scenarios:
            with self.subTest(typ=typ,key=key,val=val):
                x=example_plan()
                x[typ][n][key]=val
                with self.assertRaises(PlanReject):
                    validate_plan(x)
        x=example_plan();x["walls"][0]["authoritative_rebuild"]=True
        with self.assertRaisesRegex(PlanReject,"unsupported/missing"):
            validate_plan(x)
        x=example_plan();x["rooms"]=[{"id":"room_001"}]
        with self.assertRaises(PlanReject):
            validate_plan(x)

    def test_duplicates_and_hosted_overlapping_openings(self):
        x=example_plan();x["walls"][1]["id"]="wall_001"
        with self.assertRaisesRegex(PlanReject,"Duplicate wall"):
            validate_plan(x)
        x=example_plan();x["openings"][1]["id"]="wall_001"
        with self.assertRaisesRegex(PlanReject,"Duplicate/reused"):
            validate_plan(x)
        x=example_plan();x["openings"].append({
            "id":"door_002","kind":"door","host_wall_id":"wall_001",
            "offset_mm":2000,"width_mm":400,"locked":False
        })
        with self.assertRaisesRegex(PlanReject,"Overlapping"):
            validate_plan(x)
        x["openings"][-1]["offset_mm"]=2100
        validate_plan(x)  # touching boundaries are allowed

    def test_bounds(self):
        x=example_plan();x["walls"]=[]
        with self.assertRaises(PlanReject):validate_plan(x)
        x=example_plan();x["walls"][0]["end_mm"]=[1_000_001,0]
        with self.assertRaises(PlanReject):validate_plan(x)
        x=example_plan();x["openings"][0]["offset_mm"]=4900
        with self.assertRaises(PlanReject):validate_plan(x)


if __name__=="__main__":
    unittest.main()
