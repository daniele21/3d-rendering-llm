"""Independent real-Blender re-open + literal mesh geometry assertions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import bpy


def check(spec_path: Path, output: Path):
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    reference = {v["name"]: v for v in spec["objects"]}
    mesh = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    errors = []
    if set(mesh) != set(reference):
        errors.append("Mesh names/count mismatch")
    observed = []
    for name in sorted(mesh):
        obj = mesh[name]
        expected = reference.get(name)
        if expected is None:
            continue
        if obj.get("geometry_id") != expected.get("geometry_id", name):
            errors.append(f"{name}: stable geometry ID absent")
        for a in range(3):
            if abs(float(obj.dimensions[a]) - expected["dimensions"][a]) > .001:
                errors.append(f"{name}: dimensions mismatch axis {a}")
            if abs(float(obj.location[a]) - expected["location"][a]) > .001:
                errors.append(f"{name}: location mismatch axis {a}")
        observed.append({"name": name,
                         "center": [round(float(v), 5) for v in obj.location],
                         "dimensions": [round(float(v), 5) for v in obj.dimensions],
                         "geometry_id": obj.get("geometry_id")})
    if bpy.context.scene.camera is None:
        errors.append("No scene camera")
    result = {"passed": not errors, "errors": errors,
              "blender_version": bpy.app.version_string, "mesh_objects": observed,
              "expected_object_count": len(reference), "source_execution": False}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit("Blender scene failed geometry validation")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    x = p.parse_args(args)
    check(x.spec.resolve(), x.output.resolve())
