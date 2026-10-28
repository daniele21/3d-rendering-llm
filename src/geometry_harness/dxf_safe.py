"""Restricted, units-explicit ASCII DXF -> trusted Blender wall scene spec.

This is an architecture *vertical slice*, not a general CAD/DXF importer.
Only axis-aligned LINE and LWPOLYLINE walls, no INSERT, arcs, blocks,
external references, 3D elevation, scripts, dynamic assets or python.
All geometric values have finite and narrow safety bounds.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

class DXFReject(ValueError):
    pass

UNITS_TO_M = {4: 0.001, 5: 0.01, 6: 1.0}
_ALLOWED_ENTITY = {"LINE","LWPOLYLINE"}


def _pairs(data: str):
    if not isinstance(data, str) or len(data.encode("utf-8")) > 512_000:
        raise DXFReject("DXF input too large")
    lines = data.splitlines()
    if len(lines) % 2 != 0:
        raise DXFReject("Unpaired DXF group")
    pairs=[]
    for index in range(0,len(lines),2):
        if len(lines[index])>10 or len(lines[index+1])>256:
            raise DXFReject("Group field too large")
        try:
            group=int(lines[index].strip())
        except ValueError:
            raise DXFReject("Invalid DXF group code") from None
        pairs.append((group,lines[index+1].strip()))
    if len(pairs) > 12_000:
        raise DXFReject("Too many DXF groups")
    return pairs


def _float(value):
    try:
        x=float(value)
    except (TypeError, ValueError, OverflowError):
        raise DXFReject("Non-numeric coordinate") from None
    if not math.isfinite(x) or abs(x)>1_000_000:
        raise DXFReject("Out-of-bounds coordinate")
    return x


def _only(pair_values: list[tuple[int,str]], allowed: set[int]):
    if any(k not in allowed for k,_ in pair_values):
        raise DXFReject("Unsupported or ambiguous DXF group")
    seen={}
    for k,v in pair_values:
        if k in seen:
            raise DXFReject("Duplicate coordinate/group")
        seen[k]=v
    return seen


def _segments(kind: str, fields: list[tuple[int,str]]):
    if kind=="LINE":
        data=_only(fields,{8,10,20,30,11,21,31})
        if not {10,20,11,21}.issubset(data) or any(
            abs(_float(data.get(k,"0")))>1e-7 for k in (30,31)
        ):
            raise DXFReject("Line must have flat 2D endpoints")
        yield ((_float(data[10]),_float(data[20])),
               (_float(data[11]),_float(data[21])))
    else:
        if any(k not in {8,90,70,10,20} for k,_ in fields):
            raise DXFReject("No bulge/curve/width/elevation in safe polyline")
        data={k:v for k,v in fields if k not in {10,20}}
        if len([k for k,v in fields if k==90])!=1 or "0"!=data.get(70,"0"):
            raise DXFReject("Only open, unbulged polylines supported")
        coordinates=[(k,v) for k,v in fields if k in {10,20}]
        if len(coordinates) % 2 or not 2 <= len(coordinates)//2 <= 64:
            raise DXFReject("Invalid polyline vertex count")
        if any(coordinates[i][0]!=10 or coordinates[i+1][0]!=20
               for i in range(0,len(coordinates),2)):
            raise DXFReject("Unsupported polyline coordinate grouping")
        vertices=[(_float(coordinates[i][1]),_float(coordinates[i+1][1]))
                  for i in range(0,len(coordinates),2)]
        if int(data[90])!=len(vertices):
            raise DXFReject("Claimed vertex count differs")
        for i in range(len(vertices)-1):
            yield (vertices[i],vertices[i+1])


def compile_dxf(data: str, *, wall_height_m: float = 2.8,
                wall_thickness_m: float = 0.20) -> dict:
    height=_float(wall_height_m)
    thick=_float(wall_thickness_m)
    if not 2 <= height <= 5 or not .08 <= thick <= .6:
        raise DXFReject("Wall dimensions outside safe architectural envelope")
    pairs=_pairs(data)
    sections={}
    section=None
    i=0
    while i<len(pairs):
        key,value=pairs[i]
        if key==0 and value=="SECTION":
            if section is not None or i+1>=len(pairs) or pairs[i+1][0]!=2:
                raise DXFReject("Malformed section")
            section=pairs[i+1][1]
            if section not in {"HEADER","ENTITIES"} or section in sections:
                raise DXFReject("Only one HEADER and ENTITIES section allowed")
            sections[section]=[]
            i+=2
            continue
        if key==0 and value=="ENDSEC":
            if section is None:
                raise DXFReject("Unexpected ENDSEC")
            section=None
            i+=1
            continue
        if key==0 and value=="EOF":
            if section is not None or i!=len(pairs)-1:
                raise DXFReject("Bad EOF")
            break
        if section is None:
            raise DXFReject("Data outside supported sections")
        sections[section].append((key,value))
        i+=1
    else:
        raise DXFReject("Missing EOF")
    if set(sections)!={"HEADER","ENTITIES"}:
        raise DXFReject("Missing required DXF sections")
    h=sections["HEADER"]
    unit_candidates=[h[j+1] for j,(k,v) in enumerate(h[:-1])
                     if k==9 and v=="$INSUNITS"]
    if len(unit_candidates)!=1 or unit_candidates[0][0]!=70:
        raise DXFReject("Require exactly one explicit $INSUNITS")
    try:
        units=int(unit_candidates[0][1])
    except ValueError:
        raise DXFReject("Invalid DXF units") from None
    if units not in UNITS_TO_M:
        raise DXFReject("Only mm/cm/metre DXF units supported")
    factor=UNITS_TO_M[units]
    groups=sections["ENTITIES"]
    entities=[]
    current=None
    for k,v in groups:
        if k==0:
            if current is not None:
                entities.append(current)
            if v not in _ALLOWED_ENTITY:
                raise DXFReject("Unsafe/unsupported DXF entity")
            current=[v,[]]
        elif current is None:
            raise DXFReject("Entity data without entity type")
        else:
            current[1].append((k,v))
    if current is not None:
        entities.append(current)
    if not 1<=len(entities)<=64:
        raise DXFReject("Require 1..64 bounded wall entities")
    output=[]
    for kind,fields in entities:
        layers=[value for group,value in fields if group == 8]
        if len(layers)!=1 or layers[0] not in {"WALLS","A-WALL"}:
            raise DXFReject("Every wall must belong to an explicitly approved wall layer")
        for (x0,y0),(x1,y1) in _segments(kind,fields):
            x0,y0,x1,y1=(v*factor for v in (x0,y0,x1,y1))
            dx,dy=x1-x0,y1-y0
            length=math.hypot(dx,dy)
            if length<.1 or length>30 or not (abs(dx)<1e-5 or abs(dy)<1e-5):
                raise DXFReject("Only horizontal/vertical walls of 0.1..30m")
            if len(output)>=48:
                raise DXFReject("48-wall scene limit")
            dims=([length,thick,height] if abs(dx)>=abs(dy)
                  else [thick,length,height])
            loc=[(x0+x1)/2,(y0+y1)/2,height/2]
            output.append({
                "name":f"wall_{len(output)+1:02d}",
                "kind":"cube", "location":[round(x,6) for x in loc],
                "dimensions":[round(x,6) for x in dims]})
    if not output:
        raise DXFReject("No wall segments")
    return {
        "parser":"safe_literal_bpy_cube_v1",
        "source":"structured_dxf_ascii_v1",
        "source_units_code":units,
        "coordinate_frame":"XY_metres_up_Z",
        "walls_height_m":height, "walls_thickness_m":thick,
        "objects":output,
        "limitations":"2D axis-aligned wall centrelines only; no doors/windows/levels/rotated walls"
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--height",type=float,default=2.8)
    p.add_argument("--thickness",type=float,default=.2)
    a=p.parse_args(argv)
    if a.output.exists():
        p.error("Output must not already exist")
    spec=compile_dxf(a.input.read_text(encoding="utf8"),
                     wall_height_m=a.height, wall_thickness_m=a.thickness)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(spec,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"status":"SAFE_SPEC","n_walls":len(spec["objects"]),
                      "source_units_code":spec["source_units_code"]}))


if __name__=="__main__":
    main()
