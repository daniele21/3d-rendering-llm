# Hand-authored fixture: NOT a model result, used to test safe AST->Blender.
import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.0))
obj = bpy.context.object
obj.name = "tabletop"
obj.dimensions = (2, 1, .08)

bpy.ops.mesh.primitive_cube_add(size=1, location=(-.86, -.36, .48))
obj = bpy.context.object
obj.name = "leg_1"
obj.dimensions = (.08, .08, .96)

bpy.ops.mesh.primitive_cube_add(size=1, location=(-.86, .36, .48))
obj = bpy.context.object
obj.name = "leg_2"
obj.dimensions = (.08, .08, .96)

bpy.ops.mesh.primitive_cube_add(size=1, location=(.86, -.36, .48))
obj = bpy.context.object
obj.name = "leg_3"
obj.dimensions = (.08, .08, .96)

bpy.ops.mesh.primitive_cube_add(size=1, location=(.86, .36, .48))
obj = bpy.context.object
obj.name = "leg_4"
obj.dimensions = (.08, .08, .96)
