"""Trusted Blender builder for validated literal scene specifications.

Only this audited module is executed in Blender. Any model-generated Python
is parsed into data and never passed to --python, exec, eval or a shell.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def build(spec_file: Path, out: Path):
    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    if spec.get("parser") != "safe_literal_bpy_cube_v1":
        raise ValueError("Only approved safe-literal scene specs may be built")
    parts = spec.get("objects")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 48:
        raise ValueError("Invalid model parts list")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    extents = []
    for index, part in enumerate(parts):
        kind = part.get("kind")
        if kind == "cube":
            bpy.ops.mesh.primitive_cube_add(size=1, location=part["location"])
        elif kind == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=part["vertices"], radius=part["radius"],
                depth=part["depth"], location=part["location"])
        elif kind == "uv_sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=part["segments"], ring_count=part["ring_count"],
                radius=part["radius"], location=part["location"])
        else:
            raise ValueError("Unsupported safe primitive type")
        obj = bpy.context.object
        obj.name = part["name"]
        obj["geometry_id"] = part.get("geometry_id", part["name"])
        obj.dimensions = part["dimensions"]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        mat = bpy.data.materials.new(f"part_{index + 1:02d}_material")
        shade = [(.53, .32, .15), (.22, .36, .48), (.43, .48, .34)][index % 3]
        mat.diffuse_color = (*shade, 1)
        obj.data.materials.append(mat)
        for axis in range(3):
            extents.append(abs(float(obj.location[axis])) + float(obj.dimensions[axis]) / 2)
    maximum_extent = max(extents)
    center = Vector(tuple(
        sum(float(p["location"][i]) for p in parts) / len(parts)
        for i in range(3)
    ))
    offset = max(3.0, 3.8 * maximum_extent)
    bpy.ops.object.camera_add(location=(center.x + offset, center.y - offset, center.z + offset * .7))
    camera = bpy.context.object
    camera.name = "preview_camera"
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(3.8, 4.4 * maximum_extent)
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = "//preview.png"
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"), compress=False)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    params = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(params)
    build(args.spec.resolve(), args.out.resolve())
