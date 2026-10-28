"""Fast tests that do not require Blender or cloud inference."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from geometry_harness.cli import (
    ShowcaseError, create_g0, png_dimensions, run_blender, validate,
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

    def test_timeout_terminates_process(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ShowcaseError, "Blender timeout"):
                run_blender(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    Path(temp) / "timeout.log",
                    seconds=0.05,
                )

    def test_builder_pins_uncompressed_native_blend_format(self):
        # Search executable AST calls, not textual matches hidden inside comments.
        import ast
        from geometry_harness.cli import BUILD
        tree = ast.parse(BUILD.read_text(encoding="utf-8"))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "bpy.ops.wm.save_as_mainfile"
        ]
        self.assertEqual(len(calls), 1, "Expected exactly one executable save call")
        compression = [
            item.value for item in calls[0].keywords if item.arg == "compress"
        ]
        self.assertEqual(len(compression), 1)
        self.assertIsInstance(compression[0], ast.Constant)
        self.assertIs(compression[0].value, False)

    def test_blender_script_errors_have_nonzero_exit_policy(self):
        import inspect
        from geometry_harness.cli import create_g0
        source = inspect.getsource(create_g0)
        self.assertEqual(source.count('"--python-exit-code", "14"'), 2)

    def test_png_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "img.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\r" + b"IHDR" + struct.pack(">II", 800, 600))
            self.assertEqual(png_dimensions(path), (800, 600))


if __name__ == "__main__":
    unittest.main()
