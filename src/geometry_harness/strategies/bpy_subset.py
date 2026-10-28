"""Compile a deliberately small literal bpy geometry subset to trusted scene data.

IMPORTANT: This module *never* execs, evals, imports or runs generated code.
Only Python AST of cube primitives and literal object transforms is accepted.
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

    Repeated to 1..48 uniquely named cubes. No arbitrary code, loops,
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
            if _path(call.func) != "bpy.ops.mesh.primitive_cube_add" or call.args:
                raise UnsafeGeneratedCode("Unsupported Blender operation")
            if current is not None:
                objects.append(current)
            if len(objects) >= _MAX_OBJECTS:
                raise UnsafeGeneratedCode("Too many mesh objects")
            attrs = {}
            for kw in call.keywords:
                if not kw.arg or kw.arg not in {"size", "location"} or kw.arg in attrs:
                    raise UnsafeGeneratedCode("Unexpected cube creation argument")
                attrs[kw.arg] = _literal(kw.value)
            size = attrs.get("size", 2)
            if type(size) not in (float, int) or not math.isfinite(size) or not .001 <= size <= 30:
                raise UnsafeGeneratedCode("Cube size outside accepted range")
            current = {
                "name": f"cube_{len(objects) + 1}",
                "kind": "cube",
                "location": _vec(attrs.get("location", (0, 0, 0)), "location"),
                "dimensions": [float(size)] * 3,
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
