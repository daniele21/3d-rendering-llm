"""Blender's embedded Python builds a deterministic, editable 4-leg table."""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector

def add_box(name, center, dimensions, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj["geometry_id"] = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)

def build(folder):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    wood = bpy.data.materials.new("oak")
    wood.diffuse_color = (0.58, 0.31, 0.13, 1)
    metal = bpy.data.materials.new("dark_metal")
    metal.diffuse_color = (0.14, 0.15, 0.18, 1)

    add_box("tabletop", (0, 0, 1.0), (2.0, 1.0, .08), wood)
    for i, (x, y) in enumerate(
        [(-.86, -.36), (-.86, .36), (.86, -.36), (.86, .36)], 1
    ):
        add_box(f"leg_{i}", (x, y, .48), (.08, .08, .96), metal)

    bpy.ops.object.camera_add(location=(3.4, -4.6, 2.7))
    camera = bpy.context.object
    camera.name = "preview_camera"
    direction = Vector((0, 0, .55)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.8
    scene.camera = camera

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(folder / "preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / "scene.blend"))
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", required=True)
    build(Path(p.parse_args(args).outdir).resolve())
