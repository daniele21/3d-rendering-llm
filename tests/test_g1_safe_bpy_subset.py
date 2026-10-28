"""Generated Blender script security boundary — only AST literals, never exec."""
import unittest

from geometry_harness.strategies.bpy_subset import compile_bpy_subset, UnsafeGeneratedCode


class SafeBpySubsetTests(unittest.TestCase):
    def test_literally_expressed_cube(self):
        result = compile_bpy_subset('''import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1))
obj = bpy.context.object
obj.name = "top"
obj.dimensions = (2, 1, .10)
''')
        self.assertEqual(result["objects"][0]["name"], "top")
        self.assertEqual(result["objects"][0]["dimensions"], [2, 1, .1])
        self.assertFalse(result["source_execution"])

    def test_square_scale_is_supported_and_bounded(self):
        result = compile_bpy_subset('''import bpy
bpy.ops.mesh.primitive_cube_add(size=2)
obj = bpy.context.object
obj.name = "box"
obj.scale = (.5, 1, 1.5)
''')
        self.assertEqual(result["objects"][0]["dimensions"], [1, 2, 3])

    def test_forbid_imports_network_file_and_exec(self):
        unsafe = (
            "import os\nos.system('id')",
            "import bpy\nimport socket",
            "import bpy\nbpy.ops.wm.save_as_mainfile(filepath='/tmp/test.blend')",
            "import bpy\nexec('print(123)')",
            "import bpy\nfor i in range(4):\n bpy.ops.mesh.primitive_cube_add()",
            "import bpy\nbpy.ops.mesh.primitive_cube_add()\nobj = bpy.context.object\nobj.location = (0, float('nan'), 0)",
            "import bpy\nbpy.ops.mesh.primitive_cube_add()\nobj = bpy.context.object\nobj['other'] = 1",
        )
        for source in unsafe:
            with self.subTest(source=source), self.assertRaises(UnsafeGeneratedCode):
                compile_bpy_subset(source)

    def test_duplicate_names_and_dynamic_aliases_rejected(self):
        with self.assertRaisesRegex(UnsafeGeneratedCode, "Duplicate"):
            compile_bpy_subset('''import bpy
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.object
obj.name = "leg"
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.object
obj.name = "leg"
''')
        with self.assertRaises(UnsafeGeneratedCode):
            compile_bpy_subset('''import bpy
bpy.ops.mesh.primitive_cube_add()
other = bpy.context.object
other.name = "object"
''')

    def test_limits_and_negative_dimensions(self):
        with self.assertRaises(UnsafeGeneratedCode):
            compile_bpy_subset('''import bpy
bpy.ops.mesh.primitive_cube_add(size=1)
obj = bpy.context.object
obj.dimensions = (1, -1, 1)
''')
        with self.assertRaises(UnsafeGeneratedCode):
            compile_bpy_subset('''import bpy
bpy.ops.mesh.primitive_cube_add(location=(999, 0, 0))
''')
        with self.assertRaises(UnsafeGeneratedCode):
            compile_bpy_subset('import bpy\n' + 'bpy.ops.mesh.primitive_cube_add()\n' * 50)


if __name__ == "__main__":
    unittest.main()
