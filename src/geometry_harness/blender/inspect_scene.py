"""Executed in a fresh Blender process after reopening scene.blend."""
import argparse
import json
from pathlib import Path
import sys
import bpy

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    output = Path(p.parse_args(args).output)
    mesh = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    expected = {"tabletop": ((2, 1, .08), (0, 0, 1.0))}
    for i, (x, y) in enumerate([(-.86, -.36), (-.86, .36), (.86, -.36), (.86, .36)], 1):
        expected[f"leg_{i}"] = ((.08, .08, .96), (x, y, .48))
    errors = []
    if set(mesh) != set(expected):
        errors.append(f"Mesh names mismatch: {sorted(mesh)}")
    for name, (dimensions, center) in expected.items():
        obj = mesh.get(name)
        if obj is None:
            continue
        if obj.get("geometry_id") != name:
            errors.append(f"{name} missing geometry_id")
        for axis in range(3):
            if abs(float(obj.dimensions[axis]) - dimensions[axis]) > .0001:
                errors.append(f"{name}: wrong dimension {axis}")
            if abs(float(obj.location[axis]) - center[axis]) > .0001:
                errors.append(f"{name}: wrong center {axis}")
        if name.startswith("leg_"):
            if abs(float(obj.location.z + obj.dimensions.z / 2) - .96) > .0001:
                errors.append(f"{name}: no tabletop contact")
            if abs(float(obj.location.z - obj.dimensions.z / 2)) > .0001:
                errors.append(f"{name}: not on floor")
    result = {
        "passed": not errors,
        "errors": errors,
        "blender_version": bpy.app.version_string,
        "units": "m",
        "mesh_objects": [
            {"name": name, "geometry_id": mesh[name].get("geometry_id"),
             "dimensions": [round(float(v), 5) for v in mesh[name].dimensions],
             "center": [round(float(v), 5) for v in mesh[name].location]}
            for name in sorted(mesh)
        ],
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit("; ".join(errors))
