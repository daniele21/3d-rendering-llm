"""Real Blender E2E: the test publishes its result in the CI showcase directory."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from geometry_harness.cli import create_g0, validate, ShowcaseError


class G0ShowcaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target = Path(os.environ.get("GEOMETRY_SHOWCASE_DIR", "ci-artifacts/showcase/g0")).resolve()
        cls.target.parent.mkdir(parents=True, exist_ok=True)
        # Do not overwrite evidence from another run; the owned workspace should be fresh.
        cls.manifest = create_g0(cls.target)

    def test_real_blender_deliverables_and_geometry(self):
        m = validate(self.target)
        self.assertEqual(m["status"], "PASS")
        self.assertEqual(m["evidence_type"], "real_blender_no_ai")
        self.assertEqual(len(json.loads((self.target / "artifacts/geometry.json").read_text())["mesh_objects"]), 5)
        for path in ("index.html", "contact-sheet.png", "artifacts/scene.blend", "artifacts/preview.png"):
            self.assertGreater((self.target / path).stat().st_size, 100)

    def test_tampered_preview_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            duplicate = Path(temp) / "g0"
            shutil.copytree(self.target, duplicate)
            with (duplicate / "artifacts/preview.png").open("ab") as stream:
                stream.write(b"tampered")
            with self.assertRaisesRegex(ShowcaseError, "checksum mismatch"):
                validate(duplicate)


if __name__ == "__main__":
    unittest.main()
