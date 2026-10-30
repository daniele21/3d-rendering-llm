"""Offline GLB identity regression: original IDs vs distinct normalized stable IDs."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from geometry_harness.blender.export_verified_glb import verify_mesh_identity
from geometry_harness.evaluation.local_qwen_shape import _expected_native_mesh_ids
from geometry_harness.evaluation.upstream_shape_adapter import ShapeGateError


class FakeMesh:
    def __init__(self, name, geometry_id, vertex_count=8):
        self.name=name
        self._geometry_id=geometry_id
        self.data=SimpleNamespace(vertices=[None]*vertex_count)
    def get(self, key, default=None):
        return self._geometry_id if key=="geometry_id" else default


class ExportIdentityTests(unittest.TestCase):
    def test_normalized_qwen_stable_id_is_distinct_from_name_and_valid(self):
        inspected={
            "passed":True,
            "mesh_objects":[
                {"name":"tabletop","geometry_id":"mesh_001"},
                {"name":"leg_1","geometry_id":"mesh_002"},
            ],
        }
        expected=_expected_native_mesh_ids(inspected)
        self.assertEqual(expected["object_geometry_ids"],{
            "tabletop":"mesh_001","leg_1":"mesh_002",
        })
        meshes=[FakeMesh("tabletop","mesh_001"),FakeMesh("leg_1","mesh_002")]
        self.assertEqual(verify_mesh_identity(meshes,expected),
                         expected["object_geometry_ids"])
        # Original legacy manifest is NOT silently reinterpreted as normalized.
        with self.assertRaisesRegex(RuntimeError,"Untrusted mesh geometry_id"):
            verify_mesh_identity(meshes,{"object_ids":["tabletop","leg_1"]})

    def test_original_luna_export_still_requires_id_equals_name(self):
        meshes=[FakeMesh("top","top"),FakeMesh("base","base")]
        self.assertEqual(verify_mesh_identity(meshes,{"object_ids":["top","base"]}),
                         {"top":"top","base":"base"})
        with self.assertRaisesRegex(RuntimeError,"Untrusted mesh geometry_id"):
            verify_mesh_identity([FakeMesh("top","mesh_001"),FakeMesh("base","base")],
                                 {"object_ids":["top","base"]})

    def test_no_weakening_when_expected_map_missing_or_tampered(self):
        meshes=[FakeMesh("top","mesh_001"),FakeMesh("leg","mesh_002")]
        bad=[
            {"object_ids":["top","leg"],"object_geometry_ids":{"top":"mesh_001"}},
            {"object_ids":["top","leg"],"object_geometry_ids":{"top":"mesh_001","leg":"mesh_001"}},
            {"object_ids":["top","leg"],"object_geometry_ids":{"top":"mesh_001","leg":"../../escape"}},
            {"object_ids":["top","leg"],"object_geometry_ids":{"top":"mesh_001","leg":None}},
            {"object_ids":["top","top"]},
            {"object_ids":["top","leg"],"object_geometry_ids":{}},
        ]
        for ex in bad:
            with self.subTest(ex=ex), self.assertRaises(RuntimeError):
                verify_mesh_identity(meshes,ex)
        with self.assertRaisesRegex(RuntimeError,"Untrusted mesh geometry_id"):
            verify_mesh_identity(meshes,{
                "object_ids":["top","leg"],
                "object_geometry_ids":{"top":"mesh_002","leg":"mesh_001"},
            })
        with self.assertRaisesRegex(RuntimeError,"empty mesh"):
            verify_mesh_identity([FakeMesh("top","mesh_001",vertex_count=2)],
                {"object_ids":["top"],"object_geometry_ids":{"top":"mesh_001"}})

    def test_inspection_must_bind_unique_stable_ids(self):
        valid={"passed":True, "mesh_objects":[
            {"name":"body","geometry_id":"mesh_001"},
            {"name":"neck","geometry_id":"mesh_002"},
        ]}
        self.assertEqual(_expected_native_mesh_ids(valid)["object_ids"],["body","neck"])
        for altered in (
            {"passed":False,"mesh_objects":valid["mesh_objects"]},
            {"passed":True,"mesh_objects":[]},
            {"passed":True,"mesh_objects":[{"name":"body","geometry_id":"body"}]},
            {"passed":True,"mesh_objects":[
                {"name":"body","geometry_id":"mesh_001"},
                {"name":"body","geometry_id":"mesh_002"}]},
            {"passed":True,"mesh_objects":[
                {"name":"body","geometry_id":"mesh_001"},
                {"name":"neck","geometry_id":"mesh_001"}]},
        ):
            with self.subTest(altered=altered), self.assertRaises(ShapeGateError):
                _expected_native_mesh_ids(altered)


if __name__=="__main__":
    unittest.main()
