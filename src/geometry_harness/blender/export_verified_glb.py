"""Trusted export of independently validated Blender mesh objects to GLB.

No model-generated Python executes here. Legacy scenes that use object name
as geometry_id remain supported; normalized scenes must supply an explicit
name -> stable geometry_id map from SHA-verified independent inspection.
Never permit a name-only expected list to bypass a distinct stable ID.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def verify_mesh_identity(meshes, expected: dict) -> dict[str, str]:
    """Strict object-name and stable-ID gate, independent of Blender runtime.

    Legacy export manifests list only object_ids and require geometry_id==name.
    The normalized generator instead writes distinct stable mesh_NNN IDs. Such
    exports are accepted ONLY with an explicit, nonambiguous mapping from a
    separately verified scene inspection; missing/wrong IDs fail closed.
    """
    if not isinstance(expected, dict):
        raise RuntimeError("Invalid GLB expected-object manifest")
    names = expected.get("object_ids")
    if (not isinstance(names, list) or not 1 <= len(names) <= 48
            or any(type(v) is not str or not v or len(v) > 128 for v in names)
            or len(set(names)) != len(names)):
        raise RuntimeError("Invalid expected mesh names/count")
    if not 1 <= len(meshes) <= 48 or {o.name for o in meshes} != set(names):
        raise RuntimeError("Validated object identity mismatch")

    mapping = expected.get("object_geometry_ids")
    if mapping is None:
        # Backwards-compatible legacy contract is still STRICT name equality.
        mapping = {name: name for name in names}
    else:
        if (not isinstance(mapping, dict)
                or set(mapping) != set(names)
                or any(type(v) is not str
                       or not re.fullmatch(r"mesh_[0-9]{3}", v)
                       for v in mapping.values())
                or len(set(mapping.values())) != len(mapping)):
            raise RuntimeError("Invalid explicit stable mesh ID mapping")

    for obj in meshes:
        if (obj.get("geometry_id") != mapping[obj.name]
                or len(obj.data.vertices) < 3):
            raise RuntimeError(f"Untrusted mesh geometry_id or empty mesh: {obj.name}")
    return mapping


def main():
    import bpy

    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    parser=argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    x=parser.parse_args(args)
    if bpy.app.autoexec_fail is False and bpy.context.preferences.filepaths.use_scripts_auto_execute:
        raise RuntimeError("Auto-execute must be disabled for scorer exports")
    expected=json.loads(x.expected.read_text(encoding="utf8"))
    meshes=[o for o in bpy.data.objects if o.type=="MESH"]
    verified_ids = verify_mesh_identity(meshes, expected)
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
             "geometry_id_verification":"explicit_stable_ids" if
                 "object_geometry_ids" in expected else "legacy_id_equals_name",
             "verified_geometry_ids":verified_ids,
             "source_code_executed":False}
    (x.out.parent/"glb-export.json").write_text(json.dumps(summary,indent=2)+"\n")


if __name__=="__main__":
    main()
