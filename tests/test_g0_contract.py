"""Fast tests that do not require Blender or cloud inference."""
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from geometry_harness.cli import (
    ShowcaseError, blender_binary, create_g0, png_dimensions, validate,
)


class ContractTests(unittest.TestCase):
    def test_missing_binary_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"BLENDER_BIN": str(Path(temp) / "missing")}):
                with self.assertRaisesRegex(ShowcaseError, "BLENDER_BIN not found"):
                    create_g0(Path(temp) / "run")
            self.assertFalse((Path(temp) / "run").exists())

    def test_bad_png_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fake.png"
            path.write_bytes(b"not a png")
            with self.assertRaisesRegex(ShowcaseError, "valid PNG"):
                png_dimensions(path)

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ShowcaseError, "Missing showcase manifest"):
                validate(Path(temp))

    def test_png_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "img.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\r" + b"IHDR" + struct.pack(">II", 800, 600))
            self.assertEqual(png_dimensions(path), (800, 600))


if __name__ == "__main__":
    unittest.main()
