"""Real ezdxf unannotated CAD LINE mapping, no silently generated semantics."""
import hashlib
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from geometry_harness.domains.architecture.importer_reviewed import (
    DXFAdapterReject, import_supervised_line_plan
)
HAVE_EZDXF=importlib.util.find_spec("ezdxf") is not None


@unittest.skipUnless(HAVE_EZDXF,"CI with pinned real ezdxf must run tests")
class SupervisedDXFTests(unittest.TestCase):
    def create(self, root, *, shift_door=0, unknown=False, unit=4):
        import ezdxf
        doc=ezdxf.new("R2010")
        doc.header["$INSUNITS"]=unit
        for layer in ("A-WALL","A-DOOR","A-WINDOW"):
            doc.layers.new(layer)
        m=doc.modelspace()
        wall=m.add_line((0,0),(5000,0),dxfattribs={"layer":"A-WALL"})
        m.add_line((5000,0),(5000,4000),dxfattribs={"layer":"A-WALL"})
        door=m.add_line((1200,shift_door),(2100,shift_door),
                        dxfattribs={"layer":"A-DOOR"})
        if unknown:
            m.add_circle((2500,500),300)
        source=root/"plan-original.dxf";doc.saveas(source)
        payload={
            "schema_version":1,
            "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "review_ticket_id":"review_001",
            "opening_hosts":{door.dxf.handle.upper():f"wall_{wall.dxf.handle.upper()}_1"},
        }
        return source,payload

    def test_source_sha_all_handles_and_meters_intact(self):
        with TemporaryDirectory() as td:
            src, mapping=self.create(Path(td))
            digest=hashlib.sha256(src.read_bytes()).hexdigest()
            out=import_supervised_line_plan(src,mapping,thickness_mm=150)
            p=out["plan"]
            self.assertEqual(out["mapping_status"],"PENDING_HUMAN_CONFIRMATION")
            self.assertFalse(out["authorizes_edit"])
            self.assertTrue(out["source_dxf_not_modified"])
            self.assertEqual(p["openings"][0]["offset_mm"],1200)
            self.assertEqual(p["openings"][0]["width_mm"],900)
            self.assertEqual(p["openings"][0]["kind"],"door")
            self.assertTrue(p["openings"][0]["locked"])
            self.assertTrue(all(w["locked"] and w["structural_status"]=="unknown"
                                for w in p["walls"]))
            self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),digest)

    def test_missing_or_wrong_mapping_rejected(self):
        with TemporaryDirectory() as td:
            src,mapping=self.create(Path(td))
            cases=[
                {"opening_hosts":{}},
                {"opening_hosts":{"AABBCC":"wall_123_1"}},
                {"source_sha256":"f"*64},
                {"review_ticket_id":"../unsafe"},
                {"opening_hosts":{next(iter(mapping["opening_hosts"])):"wall_UNKNOWN_1"}},
            ]
            for change in cases:
                data={**mapping,**change}
                with self.subTest(change=change),self.assertRaises(DXFAdapterReject):
                    import_supervised_line_plan(src,data,thickness_mm=150)

    def test_cad_semantics_rejected_if_door_outside_host_or_unmodeled(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source,mapping=self.create(root,shift_door=100)
            with self.assertRaisesRegex(DXFAdapterReject,"host wall"):
                import_supervised_line_plan(source,mapping,thickness_mm=150)
            source,mapping=self.create(root,unknown=True)
            with self.assertRaisesRegex(DXFAdapterReject,"Unsupported entity"):
                import_supervised_line_plan(source,mapping,thickness_mm=150)
            source,mapping=self.create(root,unit=0)
            with self.assertRaisesRegex(DXFAdapterReject,"INSUNITS"):
                import_supervised_line_plan(source,mapping,thickness_mm=150)

    def test_reject_noninteger_thickness_before_dxf_parsing(self):
        with TemporaryDirectory() as td:
            src,mapping=self.create(Path(td))
            for thick in (True,150.5,0,None):
                with self.subTest(value=thick),self.assertRaises(DXFAdapterReject):
                    import_supervised_line_plan(src,mapping,thickness_mm=thick)

if __name__=="__main__":
    unittest.main()
