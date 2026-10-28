"""Restricted ASCII DXF -> editable, native Blender wall geometry."""
import unittest
from pathlib import Path

from geometry_harness.dxf_safe import compile_dxf, DXFReject

FIXTURE=Path(__file__).resolve().parent/"fixtures"/"arch01_room_mm.dxf"


class SafeDXFTests(unittest.TestCase):
    def test_mm_room_produces_four_metric_walls(self):
        spec=compile_dxf(FIXTURE.read_text())
        self.assertEqual(spec["parser"],"safe_literal_bpy_cube_v1")
        self.assertEqual(spec["source_units_code"],4)
        self.assertEqual([p["name"] for p in spec["objects"]],
                         ["wall_01","wall_02","wall_03","wall_04"])
        self.assertEqual(spec["objects"][0]["dimensions"],[6,.2,2.8])
        self.assertEqual(spec["objects"][1]["dimensions"],[.2,4,2.8])
        self.assertEqual(spec["objects"][0]["location"],[3,0,1.4])
        self.assertEqual(spec["coordinate_frame"],"XY_metres_up_Z")

    def test_banned_entities_units_bulges_diagonals_and_bad_numbers(self):
        template=FIXTURE.read_text()
        cases=[
            template.replace("$INSUNITS","$SOMETHING"),
            template.replace("\n70\n4\n","\n70\n0\n"),
            template.replace("0\nLINE\n8\nWALLS","0\nINSERT\n8\nWALLS",1),
            template.replace("11\n6000\n21\n0\n","11\n6000\n21\n3000\n",1),
            template.replace("11\n6000\n21\n0\n","11\nNaN\n21\n0\n",1),
            template.replace("11\n6000\n21\n0\n","11\n100000000000000000\n21\n0\n",1),
            template.replace("0\nEOF\n","0\nENDSEC\n0\nEOF\n"),
            template.replace("10\n0\n20\n0\n","10\n0\n20\n0\n42\n0.2\n",1)
        ]
        for bad in cases:
            with self.subTest(first=bad[:120]),self.assertRaises(DXFReject):
                compile_dxf(bad)

    def test_unknown_or_missing_wall_layer_is_rejected(self):
        original=FIXTURE.read_text()
        for wrong in (original.replace("8\nWALLS","8\nFURNITURE",1),
                      original.replace("8\nWALLS\n","",1),
                      original.replace("8\nWALLS\n","8\nWALLS\n8\nWALLS\n",1)):
            with self.subTest(wrong=wrong[:90]),self.assertRaises(DXFReject):
                compile_dxf(wrong)
        approved=compile_dxf(original.replace("8\nWALLS","8\nA-WALL"))
        self.assertEqual(len(approved["objects"]),4)

    def test_no_guessing_units_and_scope(self):
        with self.assertRaises(DXFReject):
            compile_dxf(FIXTURE.read_text(),wall_height_m=80)
        with self.assertRaises(DXFReject):
            compile_dxf(FIXTURE.read_text(),wall_thickness_m=.001)
        with self.assertRaises(DXFReject):
            compile_dxf(FIXTURE.read_text() * 3000)

    def test_lwpolyline_axis_aligned_explicit_open(self):
        base=FIXTURE.read_text()
        start=base.index("0\nLINE\n")
        end=base.index("0\nENDSEC\n",start)
        poly=("0\nLWPOLYLINE\n8\nWALLS\n90\n3\n70\n0\n"
              "10\n0\n20\n0\n10\n3000\n20\n0\n10\n3000\n20\n2000\n")
        doc=base[:start]+poly+base[end:]
        scene=compile_dxf(doc)
        self.assertEqual(len(scene["objects"]),2)
        self.assertEqual(scene["objects"][0]["dimensions"],[3,.2,2.8])
        self.assertEqual(scene["objects"][1]["dimensions"],[.2,2,2.8])
        with self.assertRaises(DXFReject):
            compile_dxf(doc.replace("90\n3\n","90\n6\n"))


if __name__=="__main__":
    unittest.main()
