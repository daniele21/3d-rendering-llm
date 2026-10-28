# ARCH-01 / ARCH-02 — Structured 2D → 3D architecture vertical

Status: **FIRST RESTRICTED DXF WALL SLICE IMPLEMENTED, REAL MAC PASS; COMPLETE ARCH-01 STILL OPEN** · 2026-10-28. This is **not** the existing generated-2D-reference experiment [EX-03 #10](https://github.com/daniele21/3d-rendering-llm/issues/10), which remains separate. Primary roadmap: [workstream](../workstreams/geometry-harness.md).

## First implemented slice — ARCH-01

[PR #51](https://github.com/daniele21/3d-rendering-llm/pull/51) and layer gate [#54](https://github.com/daniele21/3d-rendering-llm/pull/54) provide the first real native Blender journey from **synthetic** ASCII DXF. It supports only `LINE` and open `LWPOLYLINE` axis-aligned wall centre-lines on explicit `WALLS`/`A-WALL` layers with DXF `$INSUNITS` mm/cm/m, bounded positions and wall thickness/height. It emits the existing audited `safe_literal_bpy_cube_v1` scene-spec as **data**; no DXF Python scripts execute. The test `tests/fixtures/arch01_room_mm.dxf` makes four named rectangular walls in a 6 × 4m room; the Mac mini [run 40702702395](https://github.com/daniele21/local-runner-infra/actions/runs/40702702395) passed Blender native reopen/dimension checks and 145 private GCS objects. No partner CAD or paid inference.

```bash
PYTHONPATH=src python3 -m geometry_harness.dxf_safe --input tests/fixtures/arch01_room_mm.dxf --output /tmp/arch01-walls-scene.json
```

Important limitations: no door/window voids, curved/diagonal walls, multi-story geometry, room-closure semantics or CAD interoperability across arbitrary entities. Supporting all ten ArchitectureBench fixtures and typed targeted edits remains OPEN.

## Goal / boundaries

User imports structured 2D floorplan and obtains an **editable, measurable native Blender scene**, plus targeted revisions without reparsing/rebuilding everything. Core `geometry_harness` remains domain-agnostic; architecture-specific schema, validators and data are isolated under `domains/architecture/`. Do not present the product as certified CAD/BIM or as guaranteeing building-code compliance.

MVP supports **synthetic DXF only** with documented units, layer convention and line/polyline/block constraints. Future DWG/IFC/PDF/raster are separate acceptance tracks and must not be silently treated as equivalent. Blender is the initial geometry/render backend; no universal CAD geometry IR, CADCraft hard dependency, or architectural front-end. Library candidate ezdxf only after licence/pin/security inspection.

## Proposed minimal domain input

```json
{
  "schema_version": 1,
  "units": "m",
  "coordinate_reference": "local_xy",
  "layer_map": {"A-WALL": "wall", "A-DOOR": "door", "A-WINDOW": "window"},
  "story_height_m": 2.7,
  "wall_thickness_m": 0.15,
  "openings": [{"id": "door-01", "host_wall_id": "wall-01", "width_m": 0.9}],
  "source_dxf_sha256": "..."
}
```

This is an **architecture-domain scene spec**, not a universal model. Construction uses trusted parsing + allowlisted builder; no inference needed for explicit CAD geometry. Unknown layers, unclosed contours, overlapping/duplicated edges, missing units, conflicting references and unsupported blocks produce explicit diagnostic errors/UNKNOWN requiring user input, never guessed geometries.

## Vertical steps

1. Read DXF from a bounded local path; verify size, format, units, entity count, layer allowlist, provenance, no external file resolution without authorization; assign stable external-source IDs.
2. Parse wall/outlines/openings with explicit mapping, geometric tolerances and coordinate frame. Unsupported/ambiguous entities return diagnostics, not made-up walls.
3. Produce validated `ArchitectureSceneSpec` with walls/opening/room IDs, dimensions/semantics and source hashes. Separate input parsing from generation so the model cannot fabricate source measurements.
4. Build corresponding geometry with **trusted** Blender builder, save native scene. Do not execute free-form `bpy` from model.
5. Run geometric validators: wall connectivity/closures **where required**, dimension tolerance, door/window relative host wall and opening position, layer inclusion, self-overlap, object ID stability and scene reopen; no generic "all meshes manifold" rule.
6. Preview top/isometric + orthographic views; only optional design/style AI pass after geometric acceptance. Preserve source geometry while changing materials.
7. Accept typed incremental patch with revision journal, targeted postconditions, global non-target preservation and rollback; never silently reinterprets a private customer plan after modification.

## Synthetic fixture catalog: initial ten

1. 4×5 m room with explicit dimensions.
2. Two connected rooms, shared wall.
3. Door on wall with width and offset.
4. Window and sill placement.
5. Multi-layer wall/door/furniture mapping.
6. Missing units → reject/UNKNOWN.
7. Open boundary → precise failure, no false closed room.
8. Duplicate/overlapping segments → diagnostic.
9. Material-only change preserving all geometric transforms.
10. Door movement by 0.3 m with host-wall constraints and rollback.

Generator/scorer never see their own held-out expected geometry. All fixtures include allowed use, frozen DXF hash, expected identities/tolerances and negative assertion.

## Acceptance for ARCH-01

- On actual Mac Blender: one valid DXF → parse→domain spec→trusted geometry→preview→.blend saved and reopened independently; machine-checked dimensions/position/tolerances and human-inspectable gallery.
- At least one invalid fixture rejects correctly; no secret/case data stored in Git.
- Native object editability, stable IDs and revision evidence. Unknown layers/units are not guessed by AI.
- Compare deterministic-only and AI-assisted workflow **separately**, after agreeing on same objective output. Record wall time/cost of all phases.

## Privacy and partner onboarding

Use only synthetic public fixtures pre-NDA; partner CAD/plans, client style libraries, layer names, training examples and geometry stay outside public Git/issues/PR summaries. If access is authorized, use a private fixture store with access log, retention and customer data policy. "Runs locally" does not imply encryption, access control, isolation or regulatory compliance: each is a separate deployment acceptance requirement. See [external integration contract](external-integration-contract.md).
