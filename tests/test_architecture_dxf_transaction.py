"""Real pinned-ezdxf W2 DXF edit/reopen + adversarial semantic preservation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
import importlib.util

from geometry_harness.domains.architecture.schema import plan_sha256
from geometry_harness.domains.architecture.dxf_revision import (
    APPID, DXFRevisionError, export_verified_plan_dxf,
    import_verified_plan_dxf
)
from geometry_harness.domains.architecture.edit_door import (
    CADPatchReject, preflight_move_door, run_move_door
)

HAVE_EZDXF=importlib.util.find_spec("ezdxf") is not None


def fixture():
    return {
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":"rev_001",
        "source_sha256":hashlib.sha256(b"synthetic user approved DXF v1").hexdigest(),
        "walls":[
            {"id":"wall_001","start_mm":[0,0],"end_mm":[5000,0],
             "thickness_mm":150,"locked":False,"structural_status":"non_load_bearing"},
            {"id":"wall_002","start_mm":[5000,0],"end_mm":[5000,4000],
             "thickness_mm":200,"locked":True,"structural_status":"unknown"},
            {"id":"wall_003","start_mm":[5000,4000],"end_mm":[0,4000],
             "thickness_mm":200,"locked":True,"structural_status":"unknown"},
        ],
        "openings":[
            {"id":"door_001","kind":"door","host_wall_id":"wall_001",
             "offset_mm":1200,"width_mm":900,"locked":False},
            {"id":"window_001","kind":"window","host_wall_id":"wall_002",
             "offset_mm":500,"width_mm":700,"locked":True},
        ],
    }


def patch(plan, delta=300):
    return {
        "schema_version":1,
        "operation_id":"move_door_trial_001",
        "operation_type":"move_door","target_id":"door_001",
        "expected_plan_sha256":plan_sha256(plan),
        "expected_offset_mm":1200,"delta_mm":delta,
    }


class DoorEditPreflightTests(TestCase):
    def test_one_door_changes_without_other_geometry(self):
        original=fixture()
        unchanged=deepcopy(original)
        candidate, evidence=preflight_move_door(original,patch(original))
        self.assertEqual(original,unchanged)
        self.assertEqual(candidate["openings"][0]["offset_mm"],1500)
        self.assertEqual(candidate["openings"][1],original["openings"][1])
        self.assertEqual(candidate["walls"],original["walls"])
        self.assertEqual(candidate["source_sha256"],original["source_sha256"])
        self.assertEqual(evidence["delta_mm"],300)
        self.assertNotEqual(plan_sha256(candidate),plan_sha256(original))
        self.assertEqual(preflight_move_door(original,patch(original))[0],candidate)

    def test_reject_stale_wrong_old_locked_unknown_and_bounds(self):
        original=fixture()
        scenarios=[
            ("stale_sha",lambda p,x:p.update(expected_plan_sha256="0"*64)),
            ("stale_old",lambda p,x:p.update(expected_offset_mm=1201)),
            ("large",lambda p,x:p.update(delta_mm=1100)),
            ("zero",lambda p,x:p.update(delta_mm=0)),
            ("float",lambda p,x:p.update(delta_mm=300.0)),
            ("bool",lambda p,x:p.update(delta_mm=True)),
            ("unknown",lambda p,x:x["walls"][0].update(structural_status="unknown")),
            ("bearing",lambda p,x:x["walls"][0].update(structural_status="load_bearing")),
            ("wall_locked",lambda p,x:x["walls"][0].update(locked=True)),
            ("door_locked",lambda p,x:x["openings"][0].update(locked=True)),
            ("nonexistent",lambda p,x:p.update(target_id="door_999")),
            ("unauthorized",lambda p,x:p.update(operation_type="exec_python")),
        ]
        for label,mutate in scenarios:
            with self.subTest(label=label):
                x=deepcopy(original)
                p=patch(original)
                mutate(p,x)
                if label in {"unknown","bearing","wall_locked","door_locked"}:
                    p["expected_plan_sha256"]=plan_sha256(x)
                with self.assertRaises(CADPatchReject):
                    preflight_move_door(x,p)
        original["openings"].append({
            "id":"door_002","kind":"door","host_wall_id":"wall_001",
            "offset_mm":2250,"width_mm":900,"locked":False
        })
        with self.assertRaisesRegex(CADPatchReject,"overlap"):
            preflight_move_door(original,patch(original))

    def test_reject_door_past_wall_and_external_patch_fields(self):
        plan=fixture()
        plan["openings"][0]["offset_mm"]=4000
        p=patch(plan); p["expected_offset_mm"]=4000
        with self.assertRaisesRegex(CADPatchReject,"beyond wall"):
            preflight_move_door(plan,p)
        p=patch(fixture());p["shell_command"]="rm -rf"
        with self.assertRaisesRegex(CADPatchReject,"allowlisted"):
            preflight_move_door(fixture(),p)


@skipUnless(HAVE_EZDXF,"requires pinned ezdxf; non-optional integration CI tests it")
class RealDxfRoundtripTests(TestCase):
    def test_actual_edit_and_native_dxf_roundtrip(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            plan=fixture()
            source=root/"source-plan.json"
            source.write_text(json.dumps(plan))
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            result=run_move_door(source,patch(plan),root/"evaluation")
            self.assertEqual(result["status"],"ACCEPTED")
            self.assertTrue(result["source_unchanged"])
            self.assertTrue(result["non_targets_unchanged"])
            self.assertEqual(result["new_model_calls"],0)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),digest)
            dxf=root/"evaluation"/"candidate.dxf"
            self.assertTrue(dxf.read_bytes().startswith(b"  0"))
            replay=import_verified_plan_dxf(dxf)
            self.assertEqual(replay["openings"][0]["offset_mm"],1500)
            self.assertEqual(replay["openings"][1],plan["openings"][1])
            self.assertEqual(replay["walls"],plan["walls"])
            self.assertEqual(result["accepted_revision_sha256"],plan_sha256(replay))
            self.assertEqual(json.loads((root/"evaluation"/"accepted-plan.json").read_text()),replay)
            self.assertEqual(json.loads((root/"evaluation"/"rollback-plan.json").read_text()),plan)
            self.assertEqual(json.loads((root/"evaluation"/"transaction-manifest.json").read_text())["status"],"ACCEPTED")
            self.assertEqual(json.loads((root/"evaluation"/"operation.json").read_text())["delta_mm"],300)
            with self.assertRaises(CADPatchReject):
                run_move_door(source,patch(plan),root/"evaluation")

    def test_external_geometry_or_xdata_tamper_not_trusted(self):
        import ezdxf
        with TemporaryDirectory() as td:
            root=Path(td)
            original=fixture()
            source=root/"accepted.dxf"
            export_verified_plan_dxf(original,source)
            self.assertEqual(import_verified_plan_dxf(source),original)
            # DXF still opens but would place the rendered door incorrectly.
            doc=ezdxf.readfile(source)
            door=next(e for e in doc.modelspace() if e.dxf.layer=="A-DOOR")
            door.dxf.start=(500,500,0)
            out=root/"moved_without_meta.dxf"
            doc.saveas(out)
            with self.assertRaisesRegex(DXFRevisionError,"differs"):
                import_verified_plan_dxf(out)
            doc=ezdxf.readfile(source)
            door=next(e for e in doc.modelspace() if e.dxf.layer=="A-DOOR")
            door.discard_xdata(APPID)
            out=root/"missing_identity.dxf"
            doc.saveas(out)
            with self.assertRaises(DXFRevisionError):
                import_verified_plan_dxf(out)
            doc=ezdxf.readfile(source)
            doc.modelspace().add_circle((2000,1500),100)
            out=root/"unsupported.dxf"
            doc.saveas(out)
            with self.assertRaisesRegex(DXFRevisionError,"Only annotated"):
                import_verified_plan_dxf(out)

    def test_no_overwrite_and_oblique_opening(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            plan=fixture()
            plan["walls"][0]["end_mm"]=[3000,4000]
            plan["walls"][1]["start_mm"]=[3000,4000]
            out=root/"diagonal.dxf"
            result=export_verified_plan_dxf(plan,out)
            self.assertEqual(result["status"],"DXF_ROUNDTRIP_PASS")
            self.assertEqual(import_verified_plan_dxf(out),plan)
            with self.assertRaisesRegex(DXFRevisionError,"overwrite"):
                export_verified_plan_dxf(plan,out)


if __name__=="__main__":
    import unittest
    unittest.main()
