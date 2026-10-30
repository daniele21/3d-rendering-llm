"""Deterministic, bounded mesh-label normalization (data only, never Python execution).

A valid literal name is preserved. Invalid but printable descriptive labels are
ASCII-slugged, with stable ordinal suffixes on collisions. Exact duplicate
original names are rejected, not silently treated as separate author intent.
Mesh identity is the primitive ordinal, independent of its descriptive label.
"""
from __future__ import annotations

import re
import unicodedata

SAFE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
MAX_LABEL = 128


class UnsafeMeshName(ValueError):
    pass


def _slug(name: str, index: int) -> str:
    if (type(name) is not str or not 1 <= len(name) <= MAX_LABEL
            or not name.isprintable() or any(c in "/\\" for c in name)):
        raise UnsafeMeshName("Mesh name must be a bounded printable literal without path separators")
    latin = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", latin).strip("_-")
    if not base:
        base = f"part_{index:03d}"
    if not base[0].isalpha():
        base = "part_" + base
    base = base[:48].rstrip("_-")
    if not SAFE_NAME.fullmatch(base):
        raise UnsafeMeshName("Cannot normalize mesh name safely")
    return base


def normalize_object_names(objects: list[dict]) -> dict:
    """Mutate validated primitive specs; no calls, AST edits or string execution.

    Deterministic for a fixed primitive order. Existing valid names win over
    generated aliases, including names on *later* primitives.
    """
    originals = [obj["name"] for obj in objects]
    if len(set(originals)) != len(originals):
        raise UnsafeMeshName("Duplicate original mesh names")
    reserved = {name for name in originals if SAFE_NAME.fullmatch(name)}
    used = set(reserved)
    mapping = []
    for index, (part, original) in enumerate(zip(objects, originals), 1):
        # Validate even already-regex-safe names with the same bounded policy.
        _slug(original, index)
        if SAFE_NAME.fullmatch(original):
            alias = original
        else:
            base = _slug(original, index)
            alias = base
            suffix_no = 2
            while alias in used:
                suffix = f"__{suffix_no}"
                alias = base[:48 - len(suffix)].rstrip("_-") + suffix
                suffix_no += 1
                if suffix_no > len(objects) + 2:
                    raise UnsafeMeshName("Too many name collisions")
            if not SAFE_NAME.fullmatch(alias):
                raise UnsafeMeshName("Invalid resolved alias")
            used.add(alias)
        geometry_id = f"mesh_{index:03d}"
        part["name"] = alias
        part["geometry_id"] = geometry_id
        mapping.append({"geometry_id": geometry_id, "original_name": original,
                        "normalized_name": alias, "changed": original != alias})
    if len({obj["name"] for obj in objects}) != len(objects):
        raise UnsafeMeshName("Normalized mesh names collide")
    return {"policy": "literal_mesh_label_v1", "changes": sum(x["changed"] for x in mapping),
            "mappings": mapping}
