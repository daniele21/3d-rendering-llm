"""Trusted export from an already independently validated native scene to GLB.

Only this fixed audited repository code executes in Blender. Call Blender with
--disable-autoexec and NO provider credentials. No factory or LLM Python runs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy


def main():
    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    parser=argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    x=parser.parse_args(args)
    if bpy.app.autoexec_fail is False and bpy.context.preferences.filepaths.use_scripts_auto_execute:
        raise RuntimeError("Auto-execute must be disabled for scorer exports")
    expected=json.loads(x.expected.read_text(encoding="utf8"))
    meshes=[o for o in bpy.data.objects if o.type=="MESH"]
    if not meshes or len(meshes)>48 or {o.name for o in meshes} != set(expected["object_ids"]):
        raise RuntimeError("Validated object identity mismatch")
    if any(o.get("geometry_id")!=o.name or len(o.data.vertices)<3 for o in meshes):
        raise RuntimeError("Untrusted or empty mesh in native file")
    x.out.parent.mkdir(parents=True,exist_ok=True)
    if x.out.exists():
        raise RuntimeError("Never overwrite existing GLB")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    bpy.ops.export_scene.gltf(filepath=str(x.out.resolve()),
                              export_format="GLB",use_selection=True,
                              export_cameras=False,export_lights=False)
    if not x.out.is_file() or x.out.stat().st_size<=24 or x.out.read_bytes()[:4]!=b"glTF":
        raise RuntimeError("Real native export did not create a valid GLB")
    summary={"schema_version":1,"format":"GLB","exported_ids":sorted(o.name for o in meshes),
             "source_blender_version":bpy.app.version_string,
             "sha256":hashlib.sha256(x.out.read_bytes()).hexdigest(),
             "bytes":x.out.stat().st_size,
             "source_code_executed":False}
    (x.out.parent/"glb-export.json").write_text(json.dumps(summary,indent=2)+"\n")


if __name__=="__main__":
    main()
