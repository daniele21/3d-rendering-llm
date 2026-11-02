"""Gate real optional ezdxf parsing, fail-closed non-wall entities/layers."""
import hashlib
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from geometry_harness.domains.architecture.importer_ezdxf import (
    DXFAdapterReject, import_dxf_walls
)

EZDXF_AVAILABLE=importlib.util.find_spec("ezdxf") is not None


class EzdxfAdapterContractTests(TestCase):
    def test_absent_file_or_invalid_explicit_thickness(self):
        with self.assertRaises(DXFAdapterReject):
            import_dxf_walls(Path("/nonexistent-architecture-input.dxf"),
                             wall_thickness_mm=150)
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/"fixture.dxf"
            source.write_text("not a DXF")
            for val in (False,100.0,-10,0,None):
                with self.subTest(val=val),self.assertRaises(DXFAdapterReject):
                    import_dxf_walls(source,wall_thickness_mm=val)

    @skipUnless(EZDXF_AVAILABLE,"optional ezdxf not installed; pinned adapter CI must run")
    def test_real_ezdxf_roundtrip_wall_and_polyline(self):
        import ezdxf
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/"fixture.dxf"
            doc=ezdxf.new("R2010")
            doc.header["$INSUNITS"]=4
            doc.layers.add("A-WALL")
            doc.modelspace().add_line((0,0),(5000,0),dxfattribs={"layer":"A-WALL"})
            doc.modelspace().add_lwpolyline(
                [(5000,0),(5000,4000),(0,4000)],
                dxfattribs={"layer":"A-WALL"}
            )
            doc.saveas(source)
            original=hashlib.sha256(source.read_bytes()).hexdigest()
            plan=import_dxf_walls(source,wall_thickness_mm=150)
            self.assertEqual(len(plan["walls"]),3)
            self.assertEqual(plan["openings"],[])
            self.assertEqual(plan["source_sha256"],original)
            self.assertTrue(all(x["locked"] for x in plan["walls"]))
            self.assertTrue(all(x["structural_status"]=="unknown" for x in plan["walls"]))
            self.assertEqual(plan["walls"][0]["start_mm"],[0,0])
            self.assertEqual(plan["walls"][0]["end_mm"],[5000,0])
            self.assertEqual(plan,import_dxf_walls(source,wall_thickness_mm=150))
            self.assertEqual(original,hashlib.sha256(source.read_bytes()).hexdigest())

    @skipUnless(EZDXF_AVAILABLE,"optional ezdxf not installed; pinned adapter CI must run")
    def test_unsupported_entity_layer_and_units_refused(self):
        import ezdxf
        def make(path):
            d=ezdxf.new("R2010");d.header["$INSUNITS"]=4
            d.layers.add("A-WALL")
            d.modelspace().add_line((0,0),(5000,0),dxfattribs={"layer":"A-WALL"})
            return d
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"test.dxf"
            doc=make(p)
            doc.modelspace().add_text("ignore me",dxfattribs={"layer":"A-WALL"})
            doc.saveas(p)
            with self.assertRaisesRegex(DXFAdapterReject,"Unsupported"):
                import_dxf_walls(p,wall_thickness_mm=150)
            doc=make(p);doc.modelspace().add_line((0,0),(5000,0),dxfattribs={"layer":"UNKNOWN"})
            doc.saveas(p)
            with self.assertRaisesRegex(DXFAdapterReject,"Unmapped"):
                import_dxf_walls(p,wall_thickness_mm=150)
            doc=make(p);doc.header["$INSUNITS"]=0;doc.saveas(p)
            with self.assertRaisesRegex(DXFAdapterReject,"INSUNITS"):
                import_dxf_walls(p,wall_thickness_mm=150)
            doc=make(p)
            doc.modelspace().add_lwpolyline([(0,0,0,0,1),(5000,0)],
                                            format="xyseb",dxfattribs={"layer":"A-WALL"})
            doc.saveas(p)
            with self.assertRaisesRegex(DXFAdapterReject,"Curves"):
                import_dxf_walls(p,wall_thickness_mm=150)


if __name__=="__main__":
    import unittest
    unittest.main()
