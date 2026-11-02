"""Pinned Shapely topology on real geometry, conservative review decisions."""
import importlib.util
import unittest
from geometry_harness.domains.architecture.topology_shapely import (
    TopologyReject, assess_explicit_room, assess_plan_topology
)

HAVE_SHAPELY=importlib.util.find_spec("shapely") is not None

def make(walls):
    return {
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":"rev_001","source_sha256":"a"*64,
        "walls":[{"id":f"wall_{i+1}","start_mm":a,"end_mm":b,
                  "thickness_mm":150,"locked":True,
                  "structural_status":"unknown"}
                 for i,(a,b) in enumerate(walls)],
        "openings":[],
    }

@unittest.skipUnless(HAVE_SHAPELY,"pinned Shapely optional adapter CI exercises actual package")
class ShapelyTopologyTests(unittest.TestCase):
    def test_touching_contiguous_room_not_a_violation(self):
        plan=make([([0,0],[5000,0]),([5000,0],[5000,4000]),
                   ([5000,4000],[0,4000]),([0,4000],[0,0])])
        report=assess_plan_topology(plan)
        self.assertEqual(report["status"],"PASS_MEASURED_WALL_CENTERLINES")
        self.assertEqual(report["issue_counts"]["FAIL"],0)
        self.assertEqual(report["issue_counts"]["UNKNOWN"],0)
        self.assertEqual(report["missing_room_boundaries"],"UNKNOWN_NOT_MODELED")

    def test_centerline_overlap_fails_even_with_all_walls_locked(self):
        plan=make([([0,0],[5000,0]),([2500,0],[4500,0])])
        out=assess_plan_topology(plan)
        self.assertEqual(out["status"],"FAIL")
        self.assertEqual(out["issues"][0]["code"],"COINCIDENT_WALL_CENTERLINES")

    def test_t_or_crossing_is_review_not_fabricated_structural_clearance(self):
        crossing=make([([0,2000],[5000,2000]),([2500,0],[2500,4000])])
        out=assess_plan_topology(crossing)
        self.assertEqual(out["status"],"UNKNOWN_REQUIRES_REVIEW")
        self.assertEqual(out["issues"][0]["code"],"INTERIOR_WALL_INTERSECTION_REVIEW")
        self.assertEqual(out["structural_safety"],"UNKNOWN_NOT_ASSESSED")
        tee=make([([0,0],[5000,0]),([2500,0],[2500,4000])])
        out=assess_plan_topology(tee)
        self.assertEqual(out["status"],"UNKNOWN_REQUIRES_REVIEW")
        self.assertEqual(out["issues"][0]["code"],"WALL_T_JUNCTION_REVIEW")

    def test_explicit_room_polygon_and_bowtie_fail_closed(self):
        rect=[[0,0],[5000,0],[5000,4000],[0,4000],[0,0]]
        self.assertEqual(assess_explicit_room(None)["status"],"UNKNOWN")
        self.assertEqual(assess_explicit_room(rect)["area_m2"],20.0)
        self.assertEqual(assess_explicit_room(rect[:-1])["status"],"FAIL")
        bowtie=[[0,0],[5000,4000],[0,4000],[5000,0],[0,0]]
        self.assertEqual(assess_explicit_room(bowtie)["status"],"FAIL")
        self.assertEqual(assess_explicit_room(rect[:2]+[[True,1]]+rect[3:])["status"],"FAIL")

if __name__=="__main__":
    unittest.main()
