"""Pure stdlib geometric invariant tests for floorplans, no Blender/network."""
import unittest

from geometry_harness.domains.architecture.geometry_math import (
    GeometryReject, opening_on_wall, project_on_wall,
    room_topology_status, segments_relation
)


class ArchitectureGeometryMathTests(unittest.TestCase):
    def test_host_wall_with_bounds_and_margins(self):
        self.assertEqual(opening_on_wall((0,0),(5000,0),
                                          offset_mm=1200,width_mm=900)["status"],"PASS")
        self.assertEqual(opening_on_wall((0,0),(5000,0),
                                          offset_mm=4400,width_mm=900)["status"],"FAIL")
        self.assertEqual(opening_on_wall((0,0),(5000,0),
                                          offset_mm=0,width_mm=900,margin_mm=50)["status"],"FAIL")
        self.assertEqual(opening_on_wall((0,0),(5000,0),
                                          offset_mm=50,width_mm=900,margin_mm=50)["status"],"PASS")
        self.assertEqual(opening_on_wall((0,0),(3000,4000),
                                          offset_mm=4100,width_mm=900)["status"],"PASS")
        self.assertEqual(opening_on_wall((0,0),(3000,4000),
                                          offset_mm=4101,width_mm=900)["status"],"FAIL")

    def test_projection_uses_host_wall_not_point_guess(self):
        self.assertEqual(project_on_wall((0,0),(5000,0),(1400,0))["status"],"PASS")
        self.assertEqual(project_on_wall((0,0),(5000,0),(1400,2))["status"],"FAIL")
        self.assertEqual(project_on_wall((0,0),(5000,0),(5500,0))["status"],"FAIL")
        diag=project_on_wall((0,0),(3000,4000),(1500,2000))
        self.assertEqual(diag["projected_offset_mm"],2500)
        self.assertEqual(diag["lateral_distance_mm"],0)
        self.assertEqual(diag["status"],"PASS")

    def test_intersection_relation(self):
        cases=[
            (((0,0),(5000,0)),((2000,-500),(2000,500)),"CROSS"),
            (((0,0),(5000,0)),((5000,0),(7000,0)),"TOUCH"),
            (((0,0),(5000,0)),((2000,0),(7000,0)),"COLLINEAR_OVERLAP"),
            (((0,0),(5000,0)),((6000,0),(7000,0)),"NONE"),
            (((0,0),(5000,0)),((2000,500),(7000,500)),"NONE"),
            (((0,0),(5000,0)),((2000,0),(2000,1000)),"TOUCH"),
            (((0,0),(3000,4000)),((0,4000),(3000,0)),"CROSS")
        ]
        for (a,b),(c,d),status in cases:
            with self.subTest(status=status,a=a,b=b,c=c,d=d):
                self.assertEqual(segments_relation(a,b,c,d),status)
                self.assertEqual(segments_relation(c,d,a,b),status)

    def test_room_polygon_fails_closed(self):
        self.assertEqual(room_topology_status(None)["status"],"UNKNOWN")
        self.assertEqual(room_topology_status([(0,0),(5000,0),(5000,4000),(0,4000)])["status"],"FAIL")
        self.assertEqual(room_topology_status([
            (0,0),(5000,0),(5000,4000),(0,4000),(0,0)])["area_mm2"],20_000_000)
        self.assertEqual(room_topology_status([
            (0,0),(5000,5000),(0,5000),(5000,0),(0,0)])["status"],"FAIL")
        self.assertEqual(room_topology_status([
            (0,0),(5000,0),(5000,0),(0,5000),(0,0)])["status"],"FAIL")

    def test_rejects_ambiguous_input_and_numerics(self):
        for kw in [
            {"offset_mm":True,"width_mm":900},
            {"offset_mm":1200.0,"width_mm":900},
            {"offset_mm":1,"width_mm":-4},
            {"offset_mm":1,"width_mm":400,"margin_mm":-1}
        ]:
            with self.assertRaises(GeometryReject):
                opening_on_wall((0,0),(5000,0),**kw)
        with self.assertRaises(GeometryReject):
            project_on_wall((0,0),(5000,0),(1400.0,0))
        with self.assertRaises(GeometryReject):
            project_on_wall((0,0),(5000,0),(1400,0),max_lateral_mm=1.2)


if __name__=="__main__":
    unittest.main()
