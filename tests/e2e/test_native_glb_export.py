"""Native GLB from trusted Blender only; zero model calls, no factory Python."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from geometry_harness.g1 import create_g1, _safe_run
from geometry_harness.cli import blender_binary
from geometry_harness.evaluation.upstream_shape_adapter import EXPORT, UPSTREAM_COMMIT

FIXTURE=Path(__file__).resolve().parents[1]/"fixtures"/"g1_safe_table.py"


class TrustedGLBExporterTests(unittest.TestCase):
    def test_native_g1_to_glb_no_model_code_and_source_unchanged(self):
        root=Path(os.environ.get("GEOMETRY_SHAPE_FIXTURE_DIR",
                                 "ci-artifacts/showcase/glb-fixture")).resolve()
        self.assertFalse(root.exists())
        result=create_g1(root,fixture_source=FIXTURE.read_text())
        self.assertEqual(result["model_calls"],0)
        blend=root/"artifacts"/"scene.blend"
        before=hashlib.sha256(blend.read_bytes()).hexdigest()
        mesh=json.loads((root/"artifacts"/"geometry.json").read_text())["mesh_objects"]
        ids=root/"glb-export-expected.json"
        ids.write_text(json.dumps({"object_ids":[o["geometry_id"] for o in mesh]}))
        binary=blender_binary()
        self.assertIsNotNone(binary)
        glb=root/"glb"/"native-table.glb"
        _safe_run([binary,"-b",str(blend),"--disable-autoexec",
                   "--python-exit-code","14","--python",str(EXPORT),
                   "--","--out",str(glb),"--expected",str(ids)],
                  root/"glb-export.log",limit=120)
        self.assertTrue(glb.is_file())
        self.assertEqual(glb.read_bytes()[:4],b"glTF")
        self.assertGreater(glb.stat().st_size,256)
        manifest=json.loads((glb.parent/"glb-export.json").read_text())
        self.assertEqual(len(manifest["exported_ids"]),5)
        self.assertFalse(manifest["source_code_executed"])
        self.assertEqual(hashlib.sha256(blend.read_bytes()).hexdigest(),before)
        self.assertEqual(len(UPSTREAM_COMMIT),40)


if __name__=="__main__":
    unittest.main()
