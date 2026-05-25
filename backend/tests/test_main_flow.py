import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("EASY_MES_RUN_INTEGRATION") != "1",
    reason="Set EASY_MES_RUN_INTEGRATION=1 and provide PostgreSQL to run the MES main flow test.",
)


def idempotency_key(label: str, suffix: str) -> str:
    return f"test-{label}-{suffix}"


def auth_headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def login_as(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def post_json(client: TestClient, url: str, payload: dict, *, token: str, key: str | None = None) -> dict:
    headers = auth_headers(token, key)
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code in {200, 201}, response.text
    return response.json()


def test_mes_main_flow_from_master_data_to_traceability() -> None:
    suffix = uuid4().hex[:8].upper()
    with TestClient(app) as client:
        run_mes_main_flow(client, suffix)


def run_mes_main_flow(client: TestClient, suffix: str) -> None:
    wrong_tenant_login = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "username": "planner",
            "password": "planner123",
        },
    )
    assert wrong_tenant_login.status_code == 401, wrong_tenant_login.text

    planner_token = login_as(client, "planner", "planner123")
    operator_token = login_as(client, "operator", "operator123")
    operator_two_token = login_as(client, "operator2", "operator123")
    inspector_token = login_as(client, "inspector", "inspector123")
    dashboard_response = client.get("/api/v1/dashboard/work-orders", headers=auth_headers(planner_token))
    assert dashboard_response.status_code == 200, dashboard_response.text
    operator_dashboard_response = client.get("/api/v1/dashboard/work-orders", headers=auth_headers(operator_token))
    assert operator_dashboard_response.status_code == 403, operator_dashboard_response.text
    defect_response = client.get("/api/v1/quality/defect-reasons", headers=auth_headers(operator_token))
    assert defect_response.status_code == 200, defect_response.text

    product = post_json(
        client,
        "/api/v1/materials",
        {
            "code": f"P-E2E-{suffix}",
            "name": "端到端测试成品",
            "spec": "E2E",
            "unit": "pcs",
            "material_type": "product",
        },
        token=planner_token,
    )
    steel = post_json(
        client,
        "/api/v1/materials",
        {
            "code": f"M-E2E-ST-{suffix}",
            "name": "端到端测试圆钢",
            "spec": "D20",
            "unit": "kg",
            "material_type": "raw_material",
        },
        token=planner_token,
    )
    box = post_json(
        client,
        "/api/v1/materials",
        {
            "code": f"M-E2E-BX-{suffix}",
            "name": "端到端测试包装",
            "unit": "pcs",
            "material_type": "packing",
        },
        token=planner_token,
    )
    update_box = client.patch(
        f"/api/v1/materials/{box['id']}",
        json={"remark": "audit detail update"},
        headers=auth_headers(planner_token),
    )
    assert update_box.status_code == 200, update_box.text
    immutable_box_code = client.patch(
        f"/api/v1/materials/{box['id']}",
        json={"code": f"M-E2E-BX-RENAMED-{suffix}"},
        headers=auth_headers(planner_token),
    )
    assert immutable_box_code.status_code == 422, immutable_box_code.text
    cnc = post_json(
        client,
        "/api/v1/work-centers",
        {
            "code": f"WC-E2E-CNC-{suffix}",
            "name": "端到端 CNC",
            "work_center_type": "equipment",
        },
        token=planner_token,
    )
    qc = post_json(
        client,
        "/api/v1/work-centers",
        {
            "code": f"WC-E2E-QC-{suffix}",
            "name": "端到端质检",
            "work_center_type": "inspection",
        },
        token=planner_token,
    )
    team = post_json(
        client,
        "/api/v1/teams",
        {
            "code": f"TEAM-E2E-{suffix}",
            "name": "端到端班组",
        },
        token=planner_token,
    )
    operator = post_json(
        client,
        "/api/v1/workers",
        {
            "code": f"OP-E2E-{suffix}",
            "name": "端到端操作员",
            "worker_type": "operator",
            "team_id": team["id"],
        },
        token=planner_token,
    )
    inspector = post_json(
        client,
        "/api/v1/workers",
        {
            "code": f"QC-E2E-{suffix}",
            "name": "端到端质检员",
            "worker_type": "inspector",
            "team_id": team["id"],
        },
        token=planner_token,
    )
    post_json(
        client,
        "/api/v1/defect-reasons",
        {
            "code": f"D-E2E-{suffix}",
            "name": "端到端尺寸超差",
            "category": "尺寸",
        },
        token=planner_token,
    )
    post_json(
        client,
        "/api/v1/boms",
        {
            "material_id": product["id"],
            "version": "V1",
            "status": "active",
            "lines": [
                {"component_material_id": steel["id"], "line_no": 10, "qty_per": "1.000000"},
                {"component_material_id": box["id"], "line_no": 20, "qty_per": "1.000000"},
            ],
        },
        token=planner_token,
    )
    post_json(
        client,
        "/api/v1/routings",
        {
            "material_id": product["id"],
            "version": "V1",
            "status": "active",
            "operations": [
                {
                    "seq": 10,
                    "operation_code": "OP-E2E-CNC",
                    "operation_name": "端到端加工",
                    "work_center_id": cnc["id"],
                    "unit_time_sec": 30,
                },
                {
                    "seq": 20,
                    "operation_code": "OP-E2E-QC",
                    "operation_name": "端到端终检",
                    "work_center_id": qc["id"],
                    "unit_time_sec": 10,
                },
            ],
        },
        token=planner_token,
    )
    skill_options_response = client.get("/api/v1/operation-skill-options", headers=auth_headers(planner_token))
    assert skill_options_response.status_code == 200, skill_options_response.text
    assert {item["operation_code"] for item in skill_options_response.json()} >= {"OP-E2E-CNC", "OP-E2E-QC"}
    default_worker_response = client.get(
        "/api/v1/workers?keyword=default_operator&limit=1",
        headers=auth_headers(planner_token),
    )
    assert default_worker_response.status_code == 200, default_worker_response.text
    default_worker = default_worker_response.json()["items"][0]
    skill_update_response = client.put(
        f"/api/v1/workers/{default_worker['id']}/operation-skills",
        json={"operation_codes": ["OP-E2E-CNC", "OP-E2E-QC"]},
        headers=auth_headers(planner_token),
    )
    assert skill_update_response.status_code == 200, skill_update_response.text
    assert {item["operation_code"] for item in skill_update_response.json()} == {"OP-E2E-CNC", "OP-E2E-QC"}

    work_order = post_json(
        client,
        "/api/v1/work-orders",
        {
            "material_code": product["code"],
            "quantity": "5",
            "due_date": "2026-06-01",
            "priority": "high",
            "source": "manual",
            "external_ref": f"SO-E2E-{suffix}",
            "customer_name": "端到端客户",
        },
        token=planner_token,
        key=idempotency_key("create-wo", suffix),
    )
    assert work_order["status"] == "draft"

    work_order_no = work_order["work_order_no"]
    confirmed = post_json(client, f"/api/v1/work-orders/{work_order_no}/confirm", {}, token=planner_token)
    assert confirmed["status"] == "pending"
    kitting = post_json(client, f"/api/v1/work-orders/{work_order_no}/kitting-check", {}, token=planner_token)
    assert kitting["is_complete"] is True
    assert {item["material_code"] for item in kitting["shortage"]} == {steel["code"], box["code"]}
    missing_skill_schedule_response = client.post(
        f"/api/v1/work-orders/{work_order_no}/schedule",
        json={"operator_code": "OP-002"},
        headers=auth_headers(planner_token),
    )
    assert missing_skill_schedule_response.status_code == 400, missing_skill_schedule_response.text
    assert missing_skill_schedule_response.json()["detail"]["code"] == "OPERATOR_OPERATION_SKILL_MISSING"
    scheduled = post_json(client, f"/api/v1/work-orders/{work_order_no}/schedule", {}, token=planner_token)
    assert scheduled["status"] == "scheduled"
    list_response = client.get(f"/api/v1/work-orders?keyword={work_order_no}", headers=auth_headers(planner_token))
    assert list_response.status_code == 200, list_response.text
    list_item = next(item for item in list_response.json()["items"] if item["work_order_no"] == work_order_no)
    assert list_item["assigned_operator_codes"] == ["default_operator"]

    backfill_order = post_json(
        client,
        "/api/v1/work-orders",
        {
            "material_code": product["code"],
            "quantity": "4",
            "due_date": "2026-06-02",
            "priority": "normal",
            "source": "manual",
            "external_ref": f"SO-BACKFILL-{suffix}",
            "customer_name": "补录客户",
        },
        token=planner_token,
        key=idempotency_key("create-backfill-wo", suffix),
    )
    backfill_no = backfill_order["work_order_no"]
    post_json(client, f"/api/v1/work-orders/{backfill_no}/confirm", {}, token=planner_token)
    backfill_scheduled = post_json(client, f"/api/v1/work-orders/{backfill_no}/schedule", {}, token=planner_token)
    backfill_operation_id = backfill_scheduled["operations"][0]["id"]
    backfill_request = post_json(
        client,
        f"/api/v1/operations/{backfill_operation_id}/backfill-requests",
        {
            "started_at": "2026-05-25T01:00:00Z",
            "ended_at": "2026-05-25T01:20:00Z",
            "good_qty": "4",
            "bad_qty": "0",
            "defects": [],
            "actual_materials": [{"material_code": steel["code"], "qty": "4", "lot_no": f"BF-{suffix}"}],
            "reason": "现场先生产后补录",
        },
        token=operator_token,
        key=idempotency_key("request-backfill-op-10", suffix),
    )
    assert backfill_request["status"] == "pending"
    assert backfill_request["clock_record_id"] is None
    detail_before_approval = client.get(
        f"/api/v1/work-orders/{backfill_order['id']}",
        headers=auth_headers(planner_token),
    )
    assert detail_before_approval.status_code == 200, detail_before_approval.text
    assert detail_before_approval.json()["operations"][0]["status"] == "ready"

    pending_backfills = client.get(
        "/api/v1/operation-backfill-requests?status=pending",
        headers=auth_headers(planner_token),
    )
    assert pending_backfills.status_code == 200, pending_backfills.text
    assert any(item["id"] == backfill_request["id"] for item in pending_backfills.json()["items"])
    operator_approval = client.post(
        f"/api/v1/operation-backfill-requests/{backfill_request['id']}/approve",
        json={"review_remark": "操作员不能自审"},
        headers=auth_headers(operator_token, idempotency_key("operator-approve-backfill", suffix)),
    )
    assert operator_approval.status_code == 403, operator_approval.text
    approved_backfill = post_json(
        client,
        f"/api/v1/operation-backfill-requests/{backfill_request['id']}/approve",
        {"review_remark": "核对纸质流转卡后通过"},
        token=planner_token,
        key=idempotency_key("approve-backfill-op-10", suffix),
    )
    assert approved_backfill["status"] == "approved"
    assert approved_backfill["clock_record_id"] is not None
    detail_after_approval = client.get(
        f"/api/v1/work-orders/{backfill_order['id']}",
        headers=auth_headers(planner_token),
    )
    assert detail_after_approval.status_code == 200, detail_after_approval.text
    assert detail_after_approval.json()["status"] == "in_progress"
    assert detail_after_approval.json()["operations"][0]["status"] == "done"
    assert detail_after_approval.json()["operations"][1]["status"] == "ready"
    backfill_trace_response = client.get(
        f"/api/v1/work-orders/{backfill_no}/traceability",
        headers=auth_headers(planner_token),
    )
    assert backfill_trace_response.status_code == 200, backfill_trace_response.text
    backfill_trace = backfill_trace_response.json()
    assert len(backfill_trace["clock_records"]) == 1
    assert backfill_trace["clock_records"][0]["time_anomaly_reason"] == "backfill_approved"
    assert any(event["event_type"] == "clock" for event in backfill_trace["timeline"])

    operation_id = scheduled["operations"][0]["id"]
    workbench_response = client.get("/api/v1/operations/workbench", headers=auth_headers(operator_token))
    assert workbench_response.status_code == 200, workbench_response.text
    assert any(item["id"] == operation_id for item in workbench_response.json())
    assert scheduled["operations"][0]["assigned_operator_code"] == "default_operator"
    operator_two_ready_response = client.get("/api/v1/operations/workbench", headers=auth_headers(operator_two_token))
    assert operator_two_ready_response.status_code == 200, operator_two_ready_response.text
    assert all(item["id"] != operation_id for item in operator_two_ready_response.json())
    operator_two_scan_response = client.get(
        f"/api/v1/operations/by-qr?code={work_order_no}",
        headers=auth_headers(operator_two_token),
    )
    assert operator_two_scan_response.status_code == 403, operator_two_scan_response.text

    mismatch_response = client.post(
        f"/api/v1/operations/{operation_id}/start",
        json={"operator_code": operator["code"]},
        headers=auth_headers(operator_token, idempotency_key("start-op-mismatch", suffix)),
    )
    assert mismatch_response.status_code == 403, mismatch_response.text

    start = post_json(
        client,
        f"/api/v1/operations/{operation_id}/start",
        {},
        token=operator_token,
        key=idempotency_key("start-op-10", suffix),
    )
    assert start["status"] == "in_progress"
    cancel_running_response = client.post(
        f"/api/v1/work-orders/{work_order_no}/cancel",
        json={"reason": "端到端运行中取消保护验证"},
        headers=auth_headers(planner_token, idempotency_key("cancel-running-wo", suffix)),
    )
    assert cancel_running_response.status_code == 400, cancel_running_response.text
    assert cancel_running_response.json()["detail"]["code"] == "CANCEL_HAS_ACTIVE_WIP"
    operator_two_running_response = client.get("/api/v1/operations/workbench", headers=auth_headers(operator_two_token))
    assert operator_two_running_response.status_code == 200, operator_two_running_response.text
    assert all(item["id"] != operation_id for item in operator_two_running_response.json())
    paused = post_json(
        client,
        f"/api/v1/operations/{operation_id}/pause",
        {"reason": "端到端暂停验证"},
        token=operator_token,
        key=idempotency_key("pause-op-10", suffix),
    )
    assert paused["status"] == "paused"
    paused_workbench_response = client.get(
        "/api/v1/operations/workbench",
        headers=auth_headers(operator_token),
    )
    assert paused_workbench_response.status_code == 200, paused_workbench_response.text
    assert any(item["id"] == operation_id and item["status"] == "paused" for item in paused_workbench_response.json())
    operator_two_paused_response = client.get("/api/v1/operations/workbench", headers=auth_headers(operator_two_token))
    assert operator_two_paused_response.status_code == 200, operator_two_paused_response.text
    assert all(item["id"] != operation_id for item in operator_two_paused_response.json())

    resumed = post_json(
        client,
        f"/api/v1/operations/{operation_id}/resume",
        {"reason": "端到端恢复验证"},
        token=operator_token,
        key=idempotency_key("resume-op-10", suffix),
    )
    assert resumed["status"] == "in_progress"
    patrol = post_json(
        client,
        "/api/v1/quality/patrol",
        {
            "work_order_no": work_order_no,
            "operation_id": operation_id,
            "sample_qty": "1",
            "pass_qty": "1",
            "fail_qty": "0",
            "result": "pass",
        },
        token=inspector_token,
        key=idempotency_key("patrol", suffix),
    )
    assert patrol["result"] == "pass"
    assert patrol["inspector_code"] == "QC-001"
    inspector_mismatch_response = client.post(
        "/api/v1/quality/patrol",
        json={
            "work_order_no": work_order_no,
            "operation_id": operation_id,
            "sample_qty": "1",
            "pass_qty": "1",
            "fail_qty": "0",
            "result": "pass",
            "inspector_code": inspector["code"],
        },
        headers=auth_headers(inspector_token, idempotency_key("patrol-mismatch", suffix)),
    )
    assert inspector_mismatch_response.status_code == 403, inspector_mismatch_response.text
    over_plan_clock_response = client.post(
        f"/api/v1/operations/{operation_id}/clock",
        json={
            "good_qty": "3",
            "bad_qty": "10",
            "defects": [{"reason_code": f"D-E2E-{suffix}", "qty": "10"}],
            "actual_materials": [{"material_code": steel["code"], "qty": "13", "lot_no": f"LOT-{suffix}"}],
        },
        headers=auth_headers(operator_token, idempotency_key("clock-op-10-over-plan", suffix)),
    )
    assert over_plan_clock_response.status_code == 400, over_plan_clock_response.text
    assert over_plan_clock_response.json()["detail"]["code"] == "CLOCK_QTY_EXCEEDS_OPERATION_PLAN"
    first_clock = post_json(
        client,
        f"/api/v1/operations/{operation_id}/clock",
        {
            "good_qty": "3",
            "bad_qty": "2",
            "defects": [{"reason_code": f"D-E2E-{suffix}", "qty": "2"}],
            "actual_materials": [{"material_code": steel["code"], "qty": "5", "lot_no": f"LOT-{suffix}"}],
        },
        token=operator_token,
        key=idempotency_key("clock-op-10", suffix),
    )
    assert first_clock["next_operation_id"] is not None
    assert first_clock["operation"]["good_qty"] == "3.000000"
    assert first_clock["operation"]["bad_qty"] == "2.000000"
    assert first_clock["elapsed_seconds"] >= 0
    assert first_clock["time_anomaly"] is True
    assert first_clock["time_anomaly_reason"] == "quick_report"

    next_operation_id = first_clock["next_operation_id"]
    second_start = post_json(
        client,
        f"/api/v1/operations/{next_operation_id}/start",
        {},
        token=operator_token,
        key=idempotency_key("start-op-20", suffix),
    )
    assert second_start["status"] == "in_progress"
    assert second_start["planned_qty"] == "3.000000"
    second_clock = post_json(
        client,
        f"/api/v1/operations/{next_operation_id}/clock",
        {
            "good_qty": "3",
            "bad_qty": "0",
            "defects": [],
            "actual_materials": [],
        },
        token=operator_token,
        key=idempotency_key("clock-op-20", suffix),
    )
    assert second_clock["work_order_status"] == "completed"
    assert second_clock["operation"]["planned_qty"] == "3.000000"

    final_quality = post_json(
        client,
        "/api/v1/quality/final",
        {
            "work_order_no": work_order_no,
            "sample_qty": "2",
            "pass_qty": "2",
            "fail_qty": "0",
            "result": "pass",
        },
        token=inspector_token,
        key=idempotency_key("final", suffix),
    )
    assert final_quality["inspect_type"] == "final"
    assert final_quality["inspector_code"] == "QC-001"
    receipt = post_json(
        client,
        f"/api/v1/work-orders/{work_order_no}/receipt",
        {
            "lot_no": f"FG-{suffix}",
            "warehouse_code": "FG-01",
        },
        token=planner_token,
        key=idempotency_key("receipt", suffix),
    )
    assert receipt["work_order"]["status"] == "closed"
    assert receipt["work_order"]["actual_good_qty"] == "3.000000"
    assert receipt["work_order"]["actual_bad_qty"] == "2.000000"

    trace_response = client.get(
        f"/api/v1/work-orders/{work_order_no}/traceability",
        headers=auth_headers(planner_token),
    )
    assert trace_response.status_code == 200, trace_response.text
    trace = trace_response.json()
    assert trace["status"] == "closed"
    assert len(trace["clock_records"]) == 2
    assert any(record["time_anomaly"] for record in trace["clock_records"])
    assert trace["receipts"]
    assert any(event["event_type"] == "quality" for event in trace["timeline"])
    assert any(
        event["event_type"] == "clock" and event["detail"].get("time_anomaly") for event in trace["timeline"]
    )
    assert any(event["event_type"] == "clock" and event["actor_name"] for event in trace["timeline"])
    assert any(event["event_type"] == "quality" and event["actor_name"] for event in trace["timeline"])

    logout_response = client.post("/api/v1/auth/logout", headers=auth_headers(operator_token))
    assert logout_response.status_code == 204, logout_response.text
    revoked_response = client.get("/api/v1/auth/me", headers=auth_headers(operator_token))
    assert revoked_response.status_code == 401, revoked_response.text
    assert revoked_response.json()["detail"]["code"] == "TOKEN_REVOKED"
