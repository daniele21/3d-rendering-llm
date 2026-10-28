"""Compile a deliberately small literal bpy geometry subset to trusted scene data.

IMPORTANT: This module *never* execs, evals, imports or runs generated code.
Only Python AST of bounded cubes, cylinders and UV spheres with literal transforms is accepted.
Everything else fails closed. Not a general Blender Python security sandbox.
"""
from __future__ import annotations

import ast
import math
import re


class UnsafeGeneratedCode(ValueError):
    pass


_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
_TARGETS = {"name", "dimensions", "scale", "location"}
_ALLOWED_VARS = {"obj", "cube", "part"}
_MAX_OBJECTS = 48
_PRIMITIVES = {
    "bpy.ops.mesh.primitive_cube_add": "cube",
    "bpy.ops.mesh.primitive_cylinder_add": "cylinder",
    "bpy.ops.mesh.primitive_uv_sphere_add": "uv_sphere",
}

def _positive(value, label, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0.001 <= value <= maximum:
        raise UnsafeGeneratedCode(f"{label} must be a finite positive number <= {maximum}")
    return float(value)


def _integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise UnsafeGeneratedCode(f"{label} must be an integer between {low} and {high}")
    return value



def _path(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _path(node.value) + "." + node.attr
    return ""


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        raise UnsafeGeneratedCode("Only literal numbers, tuples and names are allowed") from None


def _vec(value, label, *, positive=False):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise UnsafeGeneratedCode(f"{label} must be a literal three-number vector")
    out = []
    for x in value:
        if type(x) not in (int, float) or not math.isfinite(x):
            raise UnsafeGeneratedCode(f"{label} has an invalid coordinate")
        if positive and not 0.001 <= x <= 30:
            raise UnsafeGeneratedCode(f"{label} must be between 0.001 and 30")
        if not positive and not -30 <= x <= 30:
            raise UnsafeGeneratedCode(f"{label} must be within +/-30")
        out.append(float(x))
    return out


def compile_bpy_subset(source: str) -> dict:
    """Accept only sequential literal bpy cube operations.

    Supported form:
      import bpy
      bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))
      obj = bpy.context.object
      obj.name = "tabletop"
      obj.dimensions = (2, 1, .1)

    Repeated to 1..48 uniquely named primitives. No arbitrary code, loops,
    functions, helper calls, materials, I/O or arbitrary bpy access.
    """
    if not isinstance(source, str) or not 1 <= len(source) <= 160000:
        raise UnsafeGeneratedCode("Invalid source length")
    try:
        root = ast.parse(source)
    except SyntaxError:
        raise UnsafeGeneratedCode("Generated source is not valid Python") from None
    objects: list[dict] = []
    current = None
    active_var = None
    for statement in root.body:
        if isinstance(statement, ast.Import):
            if len(statement.names) == 1 and statement.names[0].name == "bpy" and statement.names[0].asname is None:
                continue
            raise UnsafeGeneratedCode("Only import bpy is permitted")
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            kind = _PRIMITIVES.get(_path(call.func))
            if kind is None or call.args:
                raise UnsafeGeneratedCode("Unsupported Blender operation")
            if current is not None:
                objects.append(current)
            if len(objects) >= _MAX_OBJECTS:
                raise UnsafeGeneratedCode("Too many mesh objects")
            attrs = {}
            kwargs = {"cube": {"size", "location"},
                      "cylinder": {"radius", "depth", "vertices", "location"},
                      "uv_sphere": {"radius", "segments", "ring_count", "location"}}[kind]
            for kw in call.keywords:
                if not kw.arg or kw.arg not in kwargs or kw.arg in attrs:
                    raise UnsafeGeneratedCode("Unexpected primitive creation argument")
                attrs[kw.arg] = _literal(kw.value)
            location = _vec(attrs.get("location", (0, 0, 0)), "location")
            if kind == "cube":
                size = _positive(attrs.get("size", 2), "cube size", 30)
                dimensions = [size] * 3
                geometry = {}
            elif kind == "cylinder":
                radius = _positive(attrs.get("radius", 1), "cylinder radius", 15)
                depth = _positive(attrs.get("depth", 2), "cylinder depth", 30)
                vertices = _integer(attrs.get("vertices", 32), "cylinder vertices", 8, 64)
                dimensions = [2 * radius, 2 * radius, depth]
                geometry = {"radius": radius, "depth": depth, "vertices": vertices}
            else:
                radius = _positive(attrs.get("radius", 1), "sphere radius", 15)
                segments = _integer(attrs.get("segments", 24), "sphere segments", 8, 64)
                rings = _integer(attrs.get("ring_count", 12), "sphere ring_count", 4, 32)
                dimensions = [2 * radius] * 3
                geometry = {"radius": radius, "segments": segments, "ring_count": rings}
            current = {
                "name": f"{kind}_{len(objects) + 1}", "kind": kind,
                "location": location, "dimensions": dimensions, **geometry,
            }
            active_var = None
            continue
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                if current is None or target.id not in _ALLOWED_VARS or _path(statement.value) != "bpy.context.object":
                    raise UnsafeGeneratedCode("Unsupported assignment")
                active_var = target.id
                continue
            if not isinstance(target, ast.Attribute) or current is None:
                raise UnsafeGeneratedCode("Only active cube attributes may be changed")
            root_path = _path(target.value)
            if root_path not in ("bpy.context.object", active_var):
                raise UnsafeGeneratedCode("Object assignment references non-current cube")
            if target.attr not in _TARGETS:
                raise UnsafeGeneratedCode("Unapproved cube attribute")
            literal = _literal(statement.value)
            if target.attr == "name":
                if not isinstance(literal, str) or not _NAME.fullmatch(literal):
                    raise UnsafeGeneratedCode("Invalid or unsafe geometry name")
                current["name"] = literal
            elif target.attr == "dimensions":
                current["dimensions"] = _vec(literal, "dimensions", positive=True)
            elif target.attr == "location":
                current["location"] = _vec(literal, "location")
            elif target.attr == "scale":
                factors = _vec(literal, "scale", positive=True)
                current["dimensions"] = [a * b for a, b in zip(current["dimensions"], factors)]
                _vec(current["dimensions"], "scaled dimensions", positive=True)
            continue
        raise UnsafeGeneratedCode("Arbitrary generated Python statements are forbidden")
    if current is not None:
        objects.append(current)
    if not objects:
        raise UnsafeGeneratedCode("No permitted Blender primitives found")
    names = [obj["name"] for obj in objects]
    if len(names) != len(set(names)):
        raise UnsafeGeneratedCode("Duplicate mesh names")
    return {"schema_version": 1, "parser": "safe_literal_bpy_cube_v1",
            "objects": objects, "source_execution": False}
