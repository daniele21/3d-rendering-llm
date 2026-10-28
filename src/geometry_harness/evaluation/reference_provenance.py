"""Isolated 3DCodeBench ground-truth GLB provenance gate (NO Python execution).

A separate public release stores all 212 references in ONE tar.gz archive.
Stream through it once; retain only six reference GLBs in a *scorer-only*
directory after matching all THREE upstream task files (2 prompts + factory
script) byte-for-byte against the original frozen YipengGao dataset commit.

Never run the reference Python. Never put these GLBs/scripts into the
generator's workspace. A mismatch is a hard failure, not a score of zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import tarfile
import tempfile

from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS, EXPECTED_DATASET

ARCHIVE_REPO = "3dcodebench/3dcodebench"
ARCHIVE_SHA = "e01cafff7b85a730424c0d053aefec09144eb0b5"
ARCHIVE_FILENAME = "3dcodebench_v1.tar.gz"
# Published release checksum from the dataset croissant.json; pinned release metadata.
ARCHIVE_SHA256 = "459944518cb6e5f2a1f8de70ab273f557f4fe243b5dba7b44bb50c0e7b9563bc"
BENCHMARK_REPO = "YipengGao/3DCode"
BENCHMARK_SHA = EXPECTED_DATASET
TEXT_LIMIT = 4 * 1024 * 1024
MESH_LIMIT = 250 * 1024 * 1024


class ReferenceGateError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_files(task: str) -> tuple[str, ...]:
    return ("prompt_description.txt", "prompt_instruction.txt", task + ".py",
            task + ".glb")


def _source_file(source_root: Path, task: str, name: str) -> Path:
    # Source is an isolated *read-only scorer input* downloaded at the exact
    # benchmark SHA, not the generator's prompt-only workspace.
    path = source_root / "3DCodeBench" / task / name
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source_root):
        raise ReferenceGateError("Missing pinned scorer source file")
    return path


def _download_source_files(cache: Path) -> Path:
    from huggingface_hub import hf_hub_download
    source = cache / "original"
    source.mkdir()
    for task in EXPECTED_IDS:
        for name in expected_files(task)[:3]:
            hf_hub_download(repo_id=BENCHMARK_REPO, repo_type="dataset",
                            revision=BENCHMARK_SHA,
                            filename=f"3DCodeBench/{task}/{name}",
                            local_dir=source)
    return source


def _stream_bytes(reader, limit: int) -> bytes:
    # Do not trust an archive member size or the apparent GLB extension.
    content = reader.read(limit + 1)
    if len(content) > limit:
        raise ReferenceGateError("Archive member exceeds per-file size budget")
    return content


def _archive_member_info(member: tarfile.TarInfo) -> tuple[str, str] | None:
    parts = PurePosixPath(member.name).parts
    if ".." in parts or member.name.startswith("/"):
        raise ReferenceGateError("Unsafe archive member path")
    # Public release: data/<task>/glb/<task>.glb plus flat prompt and
    # factory files in data/<task>/. Optional top-level archive wrapper.
    if (len(parts) >= 4 and parts[-4] == "data" and parts[-2] == "glb"
        and parts[-3] in EXPECTED_IDS and parts[-1] == parts[-3] + ".glb"):
        return parts[-3], parts[-1]
    if len(parts) < 3 or parts[-3] != "data":
        return None
    task, suffix = parts[-2:]
    if task in EXPECTED_IDS and suffix in (
        f"{task}.py", "prompt_description.txt", "prompt_instruction.txt"):
        return task, suffix
    return None


def verify_archive(archive: Path, source_root: Path, output: Path,
                   *, remote_archive_verified: bool = False,
                   pinned_source_verified: bool = False) -> dict:
    if Path(archive).is_symlink() or Path(source_root).is_symlink():
        raise ReferenceGateError("Symlinked source/archive rejected")
    archive, source_root, output = archive.resolve(), source_root.resolve(), output.resolve()
    if output.exists():
        raise ReferenceGateError("Refuse to overwrite scorer reference evidence")
    if not archive.is_file() or archive.is_symlink():
        raise ReferenceGateError("Reference archive must be a regular file")
    if not source_root.is_dir() or source_root.is_symlink():
        raise ReferenceGateError("Pinned scorer-only source directory missing")
    output.parent.mkdir(parents=True, exist_ok=True)
    original = {}
    for task in EXPECTED_IDS:
        for name in expected_files(task)[:3]:
            contents = _source_file(source_root, task, name).read_bytes()
            if len(contents) > TEXT_LIMIT or not contents:
                raise ReferenceGateError("Invalid pinned prompt/factory size")
            original[(task, name)] = sha(contents)

    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".scorer-stage-") as temporary:
        root = Path(temporary)
        found = {}
        # Tar is processed sequentially; no extractall, no model/factory code
        # is run, and at most one small chunk of an untrusted GLB is in RAM.
        try:
            with tarfile.open(archive, mode="r|gz") as tar:
                for member in tar:
                    key = _archive_member_info(member)
                    if key is None:
                        continue
                    if key in found:
                        raise ReferenceGateError("Duplicate reference task member")
                    if not member.isfile() or member.size <= 0:
                        raise ReferenceGateError("Reference member must be a nonempty regular file")
                    is_mesh = key[1].endswith(".glb")
                    if member.size > (MESH_LIMIT if is_mesh else TEXT_LIMIT):
                        raise ReferenceGateError("Reference member too large")
                    reader = tar.extractfile(member)
                    if reader is None:
                        raise ReferenceGateError("Archive member unreadable")
                    with reader:
                        if is_mesh:
                            dest = root / key[0] / "glb" / key[1]
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            digest = hashlib.sha256()
                            count = 0
                            header = b""
                            with dest.open("xb") as stream:
                                while chunk := reader.read(1024 * 1024):
                                    if count + len(chunk) > MESH_LIMIT:
                                        raise ReferenceGateError("GLB exceeds bounded stream size")
                                    if len(header) < 12:
                                        header = (header + chunk)[:12]
                                    digest.update(chunk)
                                    stream.write(chunk)
                                    count += len(chunk)
                            if (count != member.size or count < 20 or len(header) != 12
                                or header[:4] != b"glTF"
                                or struct.unpack("<II", header[4:12]) != (2, count)):
                                raise ReferenceGateError("Invalid/truncated GLB v2 header")
                            found[key] = {"sha256": digest.hexdigest(), "bytes": count}
                        else:
                            value = _stream_bytes(reader, TEXT_LIMIT)
                            if len(value) != member.size:
                                raise ReferenceGateError("Truncated prompt/reference factory")
                            if sha(value) != original[key]:
                                raise ReferenceGateError(
                                    "Archive prompt/factory differs from supplied benchmark: "
                                    + key[0] + "/" + key[1])
                            found[key] = {"sha256": sha(value), "bytes": len(value)}
        except (tarfile.TarError, EOFError, OSError) as exc:
            raise ReferenceGateError("Corrupt or unreadable reference archive") from exc
        required = {(task, name) for task in EXPECTED_IDS for name in expected_files(task)}
        if set(found) != required:
            raise ReferenceGateError("All six exact prompt+factory+mesh members required")
        # Separate compressed archive hash: the 1.95GB file stays on disk.
        archive_digest = hashlib.sha256()
        with archive.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                archive_digest.update(block)
        if remote_archive_verified and archive_digest.hexdigest() != ARCHIVE_SHA256:
            raise ReferenceGateError("Pinned public archive digest differs from published checksum")
        rows = []
        for task in EXPECTED_IDS:
            rows.append({
                "task_id": task,
                "reference_glb_sha256": found[(task, task + ".glb")]["sha256"],
                "reference_glb_bytes": found[(task, task + ".glb")]["bytes"],
                "prompt_description_sha256": original[(task, "prompt_description.txt")],
                "prompt_instruction_sha256": original[(task, "prompt_instruction.txt")],
                "factory_script_sha256": original[(task, task + ".py")],
                "verified_bytes_match": True,
            })
        report = {
            "schema_version": 1,
            "reference_repository": ARCHIVE_REPO,
            "declared_archive_commit": ARCHIVE_SHA,
            "archive_filename": ARCHIVE_FILENAME,
            "archive_sha256": archive_digest.hexdigest(),
            "published_archive_sha256": ARCHIVE_SHA256,
            "published_archive_checksum_match": archive_digest.hexdigest() == ARCHIVE_SHA256,
            "archive_download_verified_at_pinned_revision": remote_archive_verified,
            "frozen_benchmark_repository": BENCHMARK_REPO,
            "frozen_benchmark_commit": BENCHMARK_SHA,
            "frozen_source_download_verified_at_pinned_revision": pinned_source_verified,
            "status": ("SIX_REFERENCE_PROMPTS_AND_SCRIPTS_MATCH_PINNED_DATASET"
                       if pinned_source_verified else "SIX_REFERENCES_MATCH_SUPPLIED_SOURCE_ONLY"),
            "match_scope": "6/6 factory script bytes + description and instruction bytes; GLB geometry remains unverified",
            "model_calls": 0,
            "official_score": None,
            "blender_version_comparable": "NOT_VERIFIED",
            "refs": rows,
        }
        (root / "reference-provenance.json").write_text(json.dumps(report, indent=2) + "\n")
        # Promotes a scorer-only directory only after all six identities match.
        os.replace(root, output)
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path,
                   help="Local public 1.95GB tar.gz already downloaded at the pinned revision")
    p.add_argument("--download-archive", action="store_true",
                   help="Explicitly download 1.95GB public archive; opt-in only")
    p.add_argument("--source-root", type=Path,
                   help="Offline pinned YipengGao benchmark: folder containing 3DCodeBench/")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    if (a.archive is None) == (not a.download_archive):
        p.error("Choose exactly one of --archive and --download-archive")
    with tempfile.TemporaryDirectory(prefix="geometry-ref-provenance-") as tmp:
        source = a.source_root if a.source_root else _download_source_files(Path(tmp))
        archive = a.archive
        if a.download_archive:
            from huggingface_hub import hf_hub_download
            # hf_hub_download may return a symlink into its content-addressed
            # cache. Resolve ONLY in this authenticated pinned-download path;
            # caller-supplied --archive symlinks still fail closed.
            archive = Path(hf_hub_download(
                repo_id=ARCHIVE_REPO, repo_type="dataset",
                revision=ARCHIVE_SHA, filename=ARCHIVE_FILENAME)).resolve()
        result = verify_archive(archive, source, a.out,
                                remote_archive_verified=a.download_archive,
                                pinned_source_verified=a.source_root is None)
        print(json.dumps({
            "status": result["status"], "refs": len(result["refs"]),
            "archive_sha256": result["archive_sha256"],
            "archive_revision_pinned": result["declared_archive_commit"],
            "official_score": None,
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
