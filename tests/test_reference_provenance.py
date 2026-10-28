"""Synthetic tiny tar release tests: six real names, zero Python execution.

These tests never download the 1.95GB public archive and never call an API.
"""
import io
import json
import struct
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.evaluation.reference_provenance import (
    EXPECTED_IDS, ReferenceGateError, verify_archive, ARCHIVE_SHA,
    BENCHMARK_SHA
)


def fixture(base: Path, *, change=None, omit=None, symlink=None):
    source=base/"pinned"
    archive=base/"refs.tar.gz"
    with tarfile.open(archive,"w:gz") as tar:
        for task in EXPECTED_IDS:
            for name in ("prompt_description.txt","prompt_instruction.txt",f"{task}.py",f"{task}.glb"):
                data=(b"glTF"+struct.pack("<II",2,76)+b"\0"*64 if name.endswith(".glb")
                      else (f"{task}/{name}\n".encode()))
                original=source/"3DCodeBench"/task/name
                if not name.endswith(".glb"):
                    original.parent.mkdir(parents=True,exist_ok=True)
                    original.write_bytes(data)
                if (task,name)==omit:
                    continue
                if (task,name)==change:
                    data+=b"mismatch"
                key=(f"3dcodebench_v1/data/{task}/glb/{name}" if name.endswith(".glb")
                     else f"3dcodebench_v1/data/{task}/{name}")
                info=tarfile.TarInfo(key)
                if (task,name)==symlink:
                    info.type=tarfile.SYMTYPE
                    info.linkname="/etc/passwd"
                    info.size=0
                    tar.addfile(info)
                else:
                    info.size=len(data)
                    tar.addfile(info,io.BytesIO(data))
    return source,archive


class ReferenceArchiveTests(unittest.TestCase):
    def test_all_six_archive_prompts_scripts_match_and_only_glbs_are_promoted(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source,archive=fixture(base)
            report=verify_archive(archive,source,base/"refs",
                                  remote_archive_verified=False,
                                  pinned_source_verified=True)
            self.assertEqual(report["status"],
                             "SIX_REFERENCE_PROMPTS_AND_SCRIPTS_MATCH_PINNED_DATASET")
            self.assertEqual(report["frozen_benchmark_commit"],BENCHMARK_SHA)
            self.assertEqual(report["declared_archive_commit"],ARCHIVE_SHA)
            self.assertFalse(report["published_archive_checksum_match"])
            self.assertFalse(report["archive_download_verified_at_pinned_revision"])
            self.assertEqual(len(report["refs"]),6)
            self.assertEqual({x["task_id"] for x in report["refs"]},set(EXPECTED_IDS))
            refs=list((base/"refs").rglob("*"))
            self.assertEqual(len([x for x in refs if x.is_file()]),7)
            self.assertFalse(any(x.suffix==".py" for x in refs))
            self.assertFalse(any(x.name.startswith("prompt_") for x in refs))
            self.assertTrue((base/"refs"/"CoffeeTable_seed0"/"glb"/"CoffeeTable_seed0.glb").is_file())
            self.assertIsNone(report["official_score"])
            self.assertEqual(json.loads((base/"refs"/"reference-provenance.json").read_text())["model_calls"],0)

    def test_supplied_source_is_not_claimed_pin_verified(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source,archive=fixture(base)
            report=verify_archive(archive,source,base/"refs")
            self.assertEqual(report["status"],"SIX_REFERENCES_MATCH_SUPPLIED_SOURCE_ONLY")
            self.assertFalse(report["frozen_source_download_verified_at_pinned_revision"])

    def test_prompt_factory_mismatch_and_missing_mesh_are_hard_blockers(self):
        for bad in ("description","factory","missing","symlink"):
            with tempfile.TemporaryDirectory() as td:
                base=Path(td)
                name=("prompt_description.txt" if bad=="description" else
                      "CoffeeTable_seed0.py" if bad=="factory" else
                      "CoffeeTable_seed0.glb")
                kw={"change":("CoffeeTable_seed0",name)} if bad in ("description","factory") else (
                    {"omit":("CoffeeTable_seed0",name)} if bad=="missing" else
                    {"symlink":("CoffeeTable_seed0",name)})
                source,archive=fixture(base,**kw)
                with self.subTest(bad=bad),self.assertRaises(ReferenceGateError):
                    verify_archive(archive,source,base/"refs",pinned_source_verified=True)
                self.assertFalse((base/"refs").exists())

    def test_rejects_existing_reference_directory_without_modification(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source,archive=fixture(base)
            output=base/"refs"
            output.mkdir()
            (output/"untouched").write_text("important")
            with self.assertRaises(ReferenceGateError):
                verify_archive(archive,source,output)
            self.assertEqual((output/"untouched").read_text(),"important")

    def test_does_not_run_arbitrary_factory_python(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source,archive=fixture(base)
            with patch("subprocess.run") as shell:
                verify_archive(archive,source,base/"refs")
                shell.assert_not_called()


if __name__=="__main__":
    unittest.main()
