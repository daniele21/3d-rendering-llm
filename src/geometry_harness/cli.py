"""G0 Geometry Harness CLI: real Blender artifacts and self-contained proof."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "blender" / "table_scene.py"
INSPECT = ROOT / "blender" / "inspect_scene.py"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ShowcaseError(RuntimeError):
    pass


def blender_binary():
    override = os.environ.get("BLENDER_BIN")
    if override:
        binary = Path(override).expanduser()
        if not binary.is_file():
            raise ShowcaseError(f"BLENDER_BIN not found: {binary}")
        return str(binary)
    return shutil.which("blender") or next(
        (str(p) for p in (
            Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            Path.home() / "Applications/Blender.app/Contents/MacOS/Blender",
        ) if p.is_file()), None
    )


def sha256(path):
    result = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def run_blender(command, logfile, seconds=180):
    logfile.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with logfile.open("w", encoding="utf-8") as log:
        p = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            rc = p.wait(timeout=seconds)
        except subprocess.TimeoutExpired as exc:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            raise ShowcaseError(f"Blender timeout after {seconds}s; see {logfile}") from exc
        if rc:
            raise ShowcaseError(f"Blender exited {rc}; see {logfile}")
    return round(time.monotonic() - start, 3)


def png_dimensions(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != PNG_MAGIC or head[12:16] != b"IHDR":
        raise ShowcaseError(f"Not a valid PNG header: {path}")
    w, h = struct.unpack(">II", head[16:24])
    if not (w > 0 and h > 0):
        raise ShowcaseError("Invalid PNG dimensions")
    return w, h


def source_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
            text=True, timeout=3,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def create_g0(output):
    if output.exists() and any(output.iterdir()):
        raise ShowcaseError(f"Output folder is not empty: {output}")
    binary = blender_binary()
    if not binary:
        raise ShowcaseError("Blender not found; install it or set BLENDER_BIN")
    artifacts = output / "artifacts"
    logs = output / "logs"
    artifacts.mkdir(parents=True, exist_ok=True)
    logs.mkdir(exist_ok=True)
    shutil.copy2(BUILD, artifacts / "generate.py")
    started = time.monotonic()
    build_duration = run_blender(
        [binary, "-b", "--factory-startup", "--python", str(BUILD),
         "--", "--outdir", str(artifacts.resolve())],
        logs / "build.txt",
    )
    if not (artifacts / "scene.blend").is_file():
        raise ShowcaseError("Blender did not save scene.blend")
    inspect_duration = run_blender(
        [binary, "-b", str((artifacts / "scene.blend").resolve()),
         "--python", str(INSPECT),
         "--", "--output", str((artifacts / "geometry.json").resolve())],
        logs / "inspect.txt",
    )
    geometry = json.loads((artifacts / "geometry.json").read_text())
    if not geometry.get("passed"):
        raise ShowcaseError(f"Geometry inspection failed: {geometry.get('errors')}")
    width, height = png_dimensions(artifacts / "preview.png")
    shutil.copy2(artifacts / "preview.png", output / "contact-sheet.png")
    checks = [
        {"name": "blend_reopened_in_fresh_process", "status": "PASS"},
        {"name": "five_meshes_and_persistent_ids", "status": "PASS"},
        {"name": "dimensions_ground_and_contacts", "status": "PASS"},
        {"name": "png_header_and_dimensions", "status": "PASS",
         "detail": f"{width}x{height}"},
    ]
    (output / "assertions.json").write_text(
        json.dumps(checks, indent=2) + "\n", encoding="utf-8"
    )
    snippet = (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>G0 Blender Showcase</title>"
        "<style>body{font:16px system-ui;background:#161a20;color:#eee;"
        "max-width:950px;margin:3rem auto;padding:1rem}"
        "img{width:100%;border-radius:14px}a{color:#a9d8ff}</style>"
        "<h1>G0 — Deterministic Blender Table</h1>"
        "<p>Real Blender render. 5 named mesh objects. No AI call.</p>"
        "<img alt='Rendered four-legged table' src='artifacts/preview.png'>"
        "<p><a href='artifacts/scene.blend'>Open scene.blend</a> · "
        "<a href='artifacts/generate.py'>Source script</a> · "
        "<a href='artifacts/geometry.json'>Measured geometry</a> · "
        "<a href='assertions.json'>Automated assertions</a></p></html>"
    )
    (output / "index.html").write_text(snippet, encoding="utf-8")
    paths = [
        "artifacts/scene.blend", "artifacts/preview.png",
        "artifacts/geometry.json", "artifacts/generate.py",
        "contact-sheet.png", "assertions.json", "index.html",
    ]
    items = [
        {"path": relative, "bytes": (output / relative).stat().st_size,
         "sha256": sha256(output / relative)}
        for relative in paths
    ]
    manifest = {
        "schema_version": 1, "milestone": "G0",
        "evidence_type": "real_blender_no_ai",
        "run_id": output.name,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "ci_runner": os.environ.get("RUNNER_NAME"),
        "source_sha": source_sha(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "blender_version": geometry["blender_version"],
        "status": "PASS", "checks": checks, "artifacts": items,
        "build_seconds": build_duration,
        "inspect_seconds": inspect_duration,
        "duration_seconds": round(time.monotonic() - started, 3),
        "model_calls": 0, "provider_cost_usd": 0,
    }
    (output / "showcase-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    validate(output)
    return manifest


def validate(output):
    output = Path(output)
    mpath = output / "showcase-manifest.json"
    if not mpath.is_file():
        raise ShowcaseError(f"Missing showcase manifest: {mpath}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    if manifest.get("milestone") != "G0" or manifest.get("status") != "PASS":
        raise ShowcaseError("G0 manifest was not marked PASS")
    if manifest.get("evidence_type") != "real_blender_no_ai":
        raise ShowcaseError("Mock or replay cannot satisfy G0")
    if any(check.get("status") != "PASS" for check in manifest.get("checks", [])):
        raise ShowcaseError("Not all acceptance checks passed")
    if len(manifest.get("checks", [])) < 4:
        raise ShowcaseError("Missing acceptance checks")
    declared = set()
    for item in manifest.get("artifacts", []):
        rel = item["path"]
        path = output / rel
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ShowcaseError("Artifact path escapes showcase root")
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ShowcaseError(f"Missing/empty/unsafe artifact: {rel}")
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ShowcaseError(f"Artifact checksum mismatch: {rel}")
        declared.add(rel)
    needed = {
        "artifacts/scene.blend", "artifacts/preview.png",
        "artifacts/geometry.json", "artifacts/generate.py",
        "contact-sheet.png", "assertions.json", "index.html",
    }
    if not needed.issubset(declared):
        raise ShowcaseError(f"Missing required deliverables: {sorted(needed - declared)}")
    with (output / "artifacts/scene.blend").open("rb") as f:
        if f.read(7) != b"BLENDER":
            raise ShowcaseError("Invalid .blend header")
    png_dimensions(output / "artifacts/preview.png")
    png_dimensions(output / "contact-sheet.png")
    measured = json.loads((output / "artifacts/geometry.json").read_text())
    if not measured.get("passed") or len(measured.get("mesh_objects", [])) != 5:
        raise ShowcaseError("Geometric assertions missing or invalid")
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(prog="geometry")
    sp = p.add_subparsers(dest="command", required=True)
    sp.add_parser("doctor")
    d = sp.add_parser("demo")
    d.add_argument("fixture", choices=["deterministic-table"])
    d.add_argument("--output", default="runs/g0")
    s = sp.add_parser("showcase")
    s.add_argument("action", nargs="?", choices=["validate"])
    s.add_argument("path", nargs="?")
    s.add_argument("--milestone", choices=["G0"])
    s.add_argument("--output", default="runs/g0")
    args = p.parse_args(argv)
    try:
        if args.command == "doctor":
            binary = blender_binary()
            print(json.dumps({"blender": binary, "python": sys.version.split()[0],
                              "platform": platform.platform()}, indent=2))
            return 0 if binary else 2
        if args.command == "showcase" and args.action == "validate":
            if not args.path:
                raise ShowcaseError("Missing bundle to validate")
            m = validate(Path(args.path))
        else:
            if args.command == "showcase" and not args.milestone:
                raise ShowcaseError("Specify --milestone G0")
            m = create_g0(Path(args.output).resolve())
        print(json.dumps({"milestone": "G0", "status": "PASS",
                          "source_sha": m["source_sha"],
                          "output": str(Path(args.path if args.command == "showcase" and args.action == "validate" else args.output).resolve())}, indent=2))
        return 0
    except (ShowcaseError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"G0 FAILED: {exc}", file=sys.stderr)
        return 1
