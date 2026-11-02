"""E0 model-facing CAD read tools: authorization and no-oracle exposure."""
import copy
import hashlib
import unittest

from geometry_harness.domains.architecture.agent_tools import (
    TOOLS, ToolCallReject, invoke_read_tool
)


def sample():
    return {
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":"rev_001",
        "source_sha256":hashlib.sha256(b"approved synthetic test").hexdigest(),
        "walls":[
            {"id":"wall_001","start_mm":[0,0],"end_mm":[5000,0],
             "thickness_mm":150,"locked":False,"structural_status":"non_load_bearing"},
            {"id":"wall_002","start_mm":[0,4000],"end_mm":[5000,4000],
             "thickness_mm":180,"locked":True,"structural_status":"unknown"}
        ],
        "openings":[
            {"id":"door_001","kind":"door","host_wall_id":"wall_001",
             "offset_mm":1200,"width_mm":900,"locked":False},
            {"id":"door_002","kind":"door","host_wall_id":"wall_002",
             "offset_mm":700,"width_mm":850,"locked":False},
        ],
    }


class AgentToolsContractTests(unittest.TestCase):
    def test_tools_have_explicit_nonmutating_contract_and_no_scorer_fields(self):
        self.assertEqual({x["name"] for x in TOOLS},
                         {"get_plan_summary","inspect_entities","query_constraints"})
        self.assertTrue(all("additionalProperties" in x["parameters"] for x in TOOLS))
        self.assertTrue(all(x["parameters"]["additionalProperties"] is False
                            for x in TOOLS))
        self.assertNotIn("reference_geometry",str(TOOLS))
        self.assertNotIn("answer_key",str(TOOLS))

    def test_summary_does_not_invent_topology_and_preserves_plan(self):
        data=sample()
        before=copy.deepcopy(data)
        result=invoke_read_tool(data,"get_plan_summary",{})
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["result"]["room_topology"],"UNKNOWN_NOT_MODELED")
        self.assertEqual(result["result"]["wall_count"],2)
        self.assertEqual(result["result"]["opening_count"],2)
        self.assertEqual(data,before)

    def test_inspect_returns_only_requested_ids(self):
        data=sample()
        result=invoke_read_tool(data,"inspect_entities",{"entity_ids":["door_001"]})
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(len(result["objects"]),1)
        self.assertEqual(result["objects"][0]["data"]["id"],"door_001")
        missing=invoke_read_tool(data,"inspect_entities",{"entity_ids":["missing_id"]})
        self.assertEqual(missing["error_code"],"UNKNOWN_ENTITY_IDS")
        self.assertEqual(missing["objects"],[])

    def test_constraints_reject_unknown_status_without_hallucinating_permission(self):
        data=sample()
        movable=invoke_read_tool(data,"query_constraints",{"target_id":"door_001"})
        self.assertEqual(movable["status"],"PASS")
        self.assertTrue(movable["authorized_for_automatic_move"])
        self.assertEqual(movable["building_code_compliance"],"UNKNOWN_NOT_CHECKED")
        blocked=invoke_read_tool(data,"query_constraints",{"target_id":"door_002"})
        self.assertEqual(blocked["status"],"UNKNOWN_REQUIRES_REVIEW")
        self.assertFalse(blocked["authorized_for_automatic_move"])
        self.assertEqual(blocked["facts"]["host_structural_status"],"unknown")

    def test_unknown_tool_extra_args_and_duplicate_ids_are_rejected(self):
        plan=sample()
        bad=[
            ("commit_revision",{}),
            ("get_plan_summary",{"dump_all":True}),
            ("inspect_entities",{"entity_ids":["door_001","door_001"]}),
            ("inspect_entities",{"entity_ids":[]}),
            ("inspect_entities",{"entity_ids":["wall_001"],"execute_python":True}),
            ("query_constraints",{"target_id":"door_001","ignore_structural":True}),
        ]
        for name,params in bad:
            with self.subTest(name=name,params=params),self.assertRaises(ToolCallReject):
                invoke_read_tool(plan,name,params)


if __name__=="__main__":
    unittest.main()
