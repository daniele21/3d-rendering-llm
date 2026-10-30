"""Offline name-normalization safety contracts; no Blender or model calls."""
import unittest

from geometry_harness.strategies.bpy_subset import compile_bpy_subset, UnsafeGeneratedCode


def source_for(*names):
    parts = ["import bpy"]
    for name in names:
        parts.extend([
            "bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,0))",
            "obj = bpy.context.object",
            f"obj.name = {name!r}",
            "obj.dimensions = (1,1,1)",
        ])
    return "\n".join(parts) + "\n"


class NameNormalizerTests(unittest.TestCase):
    def test_strict_compiler_retains_historical_rejection(self):
        with self.assertRaisesRegex(UnsafeGeneratedCode, "name"):
            compile_bpy_subset(source_for("Table top"))
        self.assertNotIn("name_normalization", compile_bpy_subset(source_for("tabletop")))

    def test_mixed_literal_names_and_stable_ids(self):
        code = source_for("Table top", "éclairage", "桌子", "Table_top")
        result = compile_bpy_subset(code, normalize_names=True)
        names = [x["name"] for x in result["objects"]]
        self.assertEqual(names, ["Table_top__2", "eclairage", "part_003", "Table_top"])
        self.assertEqual([x["geometry_id"] for x in result["objects"]],
                         ["mesh_001", "mesh_002", "mesh_003", "mesh_004"])
        m = result["name_normalization"]
        self.assertEqual(m["changes"], 3)
        self.assertEqual(m["mappings"][0]["original_name"], "Table top")
        self.assertEqual(m["mappings"][0]["normalized_name"], "Table_top__2")
        self.assertEqual(result, compile_bpy_subset(code, normalize_names=True))
        self.assertFalse(result["source_execution"])

    def test_collision_between_two_distinct_invalid_labels(self):
        r = compile_bpy_subset(source_for("Arm Chair", "Arm@Chair"), normalize_names=True)
        self.assertEqual([x["name"] for x in r["objects"]], ["Arm_Chair", "Arm_Chair__2"])

    def test_truncation_and_suffix_are_bounded(self):
        r = compile_bpy_subset(source_for("A" * 65, "A" * 64 + "."), normalize_names=True)
        self.assertEqual(len(r["objects"][0]["name"]), 48)
        self.assertEqual(len(r["objects"][1]["name"]), 48)
        self.assertTrue(r["objects"][1]["name"].endswith("__2"))

    def test_exact_duplicate_original_names_fail_closed(self):
        for name in ("leg", "Arm Chair"):
            with self.subTest(name=name), self.assertRaisesRegex(UnsafeGeneratedCode, "Duplicate"):
                compile_bpy_subset(source_for(name, name), normalize_names=True)

    def test_bad_labels_rejected_not_sanitized(self):
        for name in ("", "x" * 129, "../private", "a\\b", "bad\nname",
                     "bad\x00name", "bad\u202ename", "bad\tname"):
            with self.subTest(name=repr(name)), self.assertRaises(UnsafeGeneratedCode):
                compile_bpy_subset(source_for(name), normalize_names=True)

    def test_dangerous_ast_still_rejected(self):
        bad = (
            "import os\nos.system('touch /tmp/pwned')",
            "import bpy\nbpy.ops.mesh.primitive_cube_add()\nobj=bpy.context.object\nobj.name=__import__('os').system('id')",
            "import bpy\nfor i in range(3):\n bpy.ops.mesh.primitive_cube_add()",
            "import bpy\nbpy.ops.mesh.primitive_cube_add()\nobj=bpy.context.object\nobj.name='leg 1'\nobj.data.materials.clear()",
            "import bpy\nbpy.ops.mesh.primitive_cube_add(size=10**9)",
        )
        for code in bad:
            with self.subTest(code=code), self.assertRaises(UnsafeGeneratedCode):
                compile_bpy_subset(code, normalize_names=True)

    def test_existing_table_contract_name_is_unmodified(self):
        r = compile_bpy_subset(source_for("tabletop", "leg_1"), normalize_names=True)
        self.assertEqual(r["name_normalization"]["changes"], 0)
        self.assertEqual([x["name"] for x in r["objects"]], ["tabletop", "leg_1"])


if __name__ == "__main__":
    unittest.main()
