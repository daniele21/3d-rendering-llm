"""No model calls: model suggestions are data only, not executable CAD."""
import hashlib
import json
import unittest
from geometry_harness.domains.architecture.agent_patch_gateway import (
    agent_tool_contracts, parse_proposal_json, validate_model_proposal
)
from geometry_harness.domains.architecture.edit_door import CADPatchReject

def plan():
    return {
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":"rev_001","source_sha256":hashlib.sha256(b"synthetic").hexdigest(),
        "walls":[
            {"id":"wall_001","start_mm":[0,0],"end_mm":[5000,0],
             "thickness_mm":150,"locked":False,"structural_status":"non_load_bearing"},
            {"id":"wall_002","start_mm":[5000,0],"end_mm":[5000,4000],
             "thickness_mm":150,"locked":True,"structural_status":"unknown"},
        ],
        "openings":[
            {"id":"door_001","kind":"door","host_wall_id":"wall_001",
             "offset_mm":1200,"width_mm":900,"locked":False},
        ],
    }

class GatewayTests(unittest.TestCase):
    def test_same_request_typical_model_json_preflights_without_side_effect(self):
        data=plan(); old=json.dumps(data,sort_keys=True)
        payload=json.dumps({
            "schema_version":1,"operation_type":"move_door",
            "target_id":"door_001","delta_mm":300})
        result=validate_model_proposal(data,payload,host_operation_id="host_001")
        self.assertEqual(result["status"],"VALIDATED_PROPOSAL_NOT_COMMITTED")
        self.assertEqual(result["patch"]["expected_offset_mm"],1200)
        self.assertEqual(result["patch"]["delta_mm"],300)
        self.assertEqual(result["patch"]["operation_id"],"host_001")
        self.assertEqual(result["validation"]["geometry_status"],"PASS")
        self.assertTrue(result["validation"]["requires_host_approval"])
        self.assertEqual(old,json.dumps(data,sort_keys=True))

    def test_rejects_forged_commit_source_or_tool(self):
        specs=agent_tool_contracts()
        self.assertEqual(len(specs),4)
        names=[x["name"] for x in specs]
        self.assertNotIn("commit_revision",names)
        self.assertNotIn("write_dxf",names)
        for payload in [
            '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":300,"shell":"exec"}',
            '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":300,"delta_mm":400}',
            '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":300.0}',
            '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":true}',
            '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":0}',
            '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":-1001}',
            '{"schema_version":1,"operation_type":"execute_python","target_id":"door_001","delta_mm":300}',
            '{"schema_version":1,"operation_type":"move_door","target_id":"../escape","delta_mm":300}',
            '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":NaN}',
        ]:
            with self.subTest(payload=payload),self.assertRaises(CADPatchReject):
                parse_proposal_json(payload)

    def test_unknown_structural_never_auto_approved(self):
        data=plan()
        data["walls"][0]["structural_status"]="unknown"
        msg=json.dumps({
            "schema_version":1,"operation_type":"move_door",
            "target_id":"door_001","delta_mm":300})
        with self.assertRaisesRegex(CADPatchReject,"not approved"):
            validate_model_proposal(data,msg,host_operation_id="host_001")

    def test_noop_wrong_target_and_bounds_refuse(self):
        data=plan()
        for target,delta in [("door_missing",300),("door_001",4000),
                             ("door_001",0)]:
            payload=json.dumps({
                "schema_version":1,"operation_type":"move_door",
                "target_id":target,"delta_mm":delta})
            with self.subTest(target=target,delta=delta),self.assertRaises(CADPatchReject):
                validate_model_proposal(data,payload,host_operation_id="host_001")

if __name__=="__main__":
    unittest.main()
