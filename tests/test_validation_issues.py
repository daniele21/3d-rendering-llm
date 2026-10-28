"""Contract-driven validation. Never mistakes absent evidence for PASS."""
import unittest
from geometry_harness.validation.issues import validate, ValidationError


def fixture():
    objects = [{"name": "tabletop", "geometry_id": "tabletop",
                "center": [0, 0, 1], "dimensions": [2, 1, .08]}]
    for i, (x, y) in enumerate(((-.86,-.36),(-.86,.36),(.86,-.36),(.86,.36)), 1):
        objects.append({"name": f"leg_{i}", "geometry_id": f"leg_{i}",
                        "center": [x, y, .48], "dimensions": [.08, .08, .96]})
    return {"passed": True, "mesh_objects": objects}


def contract():
    return {"schema_version": 1, "task_id": "synthetic_table", "units": "m",
            "requirements": [
                {"id": "top_dimensions", "type": "dimensions", "object_id": "tabletop",
                 "expected_dimensions_m": [2, 1, .08], "tolerance_m": .01},
                {"id": "foot", "type": "floor_contact", "object_id": "leg_1",
                 "floor_z_m": 0, "tolerance_m": .02},
                {"id": "leg_connected", "type": "vertical_contact", "support_id": "leg_1",
                 "supported_id": "tabletop", "tolerance_m": .02},
            ]}


class GeometryIssueTests(unittest.TestCase):
    def test_explicit_table_pass(self):
        r = validate(fixture(), contract())
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["pass_count"], 3)
        self.assertTrue(r["read_only"])

    def test_disconnected_leg_is_precise_failure(self):
        g = fixture()
        g["mesh_objects"][1]["center"][2] = .30
        r = validate(g, contract())
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(r["fail_count"], 2)
        issue = next(x for x in r["issues"] if x["code"] == "vertical_contact")
        self.assertEqual(issue["affected_ids"], ["leg_1","tabletop"])
        self.assertEqual(issue["reason"], "disconnected_support")

    def test_bad_dimensions_and_missing_target(self):
        g = fixture()
        g["mesh_objects"][0]["dimensions"][0] = 2.4
        result = validate(g, contract())
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["issues"][0]["reason"], "dimension_outside_tolerance")
        g["mesh_objects"].pop(1)
        r = validate(g, contract())
        self.assertEqual(r["issues"][1]["reason"], "required_mesh_missing")

    def test_missing_or_untrusted_evidence_is_unknown(self):
        for evidence in (None, {}, {"passed":False}, {"passed":True, "mesh_objects":[]},
                         {"passed":True, "mesh_objects":[{"bad":"shape"}]}):
            with self.subTest(evidence=evidence):
                r = validate(evidence, contract())
                self.assertIn(r["status"], ("UNKNOWN","FAIL"))
                self.assertNotEqual(r["status"], "PASS")

    def test_wrong_units_unbounded_tolerance_duplicate_unsupported(self):
        for key, value in (("units","ft"), ("schema_version",2)):
            c = contract()
            c[key] = value
            with self.assertRaises(ValidationError):
                validate(fixture(), c)
        c = contract()
        c["requirements"][0]["tolerance_m"] = float("nan")
        with self.assertRaises(ValidationError):
            validate(fixture(), c)
        c = contract()
        c["requirements"][1]["id"] = "top_dimensions"
        with self.assertRaises(ValidationError):
            validate(fixture(), c)
        c = contract()
        c["requirements"][0]["type"] = "arbitrary_python"
        with self.assertRaises(ValidationError):
            validate(fixture(), c)


if __name__ == "__main__":
    unittest.main()
