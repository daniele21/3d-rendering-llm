"""Architecture registry integrity and generator/reference separation."""
import copy
import unittest
from unittest.mock import patch

from benchmarks.architecture.registry import (
    ArchitectureBenchmarkReject, generator_tasks, read_suite, verify_registry
)


class ArchitectureRegistryTests(unittest.TestCase):
    def test_exact_initial_suite_and_no_fake_completion(self):
        info=verify_registry()
        self.assertEqual(info["registered"],10)
        self.assertEqual(info["planned"],30)
        self.assertEqual(info["count_by_kind"],{
            "import":4,"rejection":4,"edit":2})
        self.assertEqual(info["status"],"VALID_INITIAL_REGISTRY_NOT_EXECUTION")
        self.assertEqual(info["executable_edit_gates"],0)
        self.assertEqual(len(generator_tasks()),10)

    def test_model_never_receives_scorer_oracle(self):
        task_list=generator_tasks()
        for task in task_list:
            self.assertEqual(set(task),{"task_id","instruction","fixture_ref"})
            self.assertNotIn("expected_outcome",task)
            self.assertNotIn("expected_change_mm",task)
        self.assertEqual(len({x["task_id"] for x in task_list}),10)

    def test_tampered_fixture_reference_is_rejected(self):
        suite=copy.deepcopy(read_suite())
        suite["cases"][0]["fixture_ref"]="fake_missing_fixture"
        with patch("benchmarks.architecture.registry.read_suite",return_value=suite):
            with self.assertRaises(ArchitectureBenchmarkReject):
                verify_registry()

    def test_wrong_task_count_and_faked_edit_success_rejected(self):
        suite=copy.deepcopy(read_suite())
        suite["cases"]=suite["cases"][:-1]
        with patch("benchmarks.architecture.registry.read_suite",return_value=suite):
            with self.assertRaises(ArchitectureBenchmarkReject):
                verify_registry()
        suite=copy.deepcopy(read_suite())
        suite["cases"][-1]["expected_outcome"]="PLAN_SCHEMA_PASS"
        with patch("benchmarks.architecture.registry.read_suite",return_value=suite):
            with self.assertRaises(ArchitectureBenchmarkReject):
                verify_registry()


if __name__=="__main__":
    unittest.main()
