"""Trusted Blender-only four-view visual evidence from an already saved scene.

This module is repository-owned, not model output; it never saves or mutates
the original .blend. It is NOT a visual judge or a reference similarity score.
Usage: blender -b scene.blend --python render_validation_views.py -- --out VIEWS
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_views(out: Path):
    if out.exists() and any(out.iterdir()):
        raise ValueError("Refusing to overwrite a view evidence directory")
    out.mkdir(parents=True, exist_ok=True)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise ValueError("No saved mesh objects to render")
    corners = [o.matrix_world @ Vector(corner) for o in meshes for corner in o.bound_box]
    center = Vector(tuple((min(v[i] for v in corners) + max(v[i] for v in corners)) / 2
                          for i in range(3)))
    extents = [max(v[i] for v in corners) - min(v[i] for v in corners)
               for i in range(3)]
    scale = max(2.5, max(extents) * 2.5)
    camera_distance = max(4, scale * 2)
    offsets = {
        "front": (0, -1, 0.32),
        "side": (1, 0, 0.32),
        "top": (0, 0, 1),
        "isometric": (1, -1, 0.9),
    }
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.display.shading.light = "STUDIO"
    rows = []
    for name, coords in offsets.items():
        offset = Vector(coords).normalized() * camera_distance
        bpy.ops.object.camera_add(location=center + offset)
        camera = bpy.context.object
        camera.name = "validation_camera_" + name
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = scale
        scene.camera = camera
        path = (out / (name + ".png")).resolve()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 100:
            raise ValueError("Real Blender failed to produce a view image")
        rows.append({"view": name, "path": path.name, "sha256": _sha256(path),
                     "bytes": path.stat().st_size})
        bpy.data.objects.remove(camera, do_unlink=True)
    (out / "views-manifest.json").write_text(json.dumps({
        "schema_version": 1, "views": rows,
        "source_scene_saved": bool(bpy.data.is_saved),
        "original_blend_modified_on_disk": False,
        "quality_judgement": "UNKNOWN_NO_VISUAL_JUDGE",
        "geometry_target_count": len(meshes),
        "blender_version": bpy.app.version_string,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    x = p.parse_args(args)
    render_views(x.out.resolve())
