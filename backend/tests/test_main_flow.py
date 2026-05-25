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
    planner_token = login_as(client, "planner", "planner123")
    operator_token = login_as(client, "operator", "operator123")
    inspector_token = login_as(client, "inspector", "inspector123")

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
    scheduled = post_json(client, f"/api/v1/work-orders/{work_order_no}/schedule", {}, token=planner_token)
    assert scheduled["status"] == "scheduled"

    operation_id = scheduled["operations"][0]["id"]
    start = post_json(
        client,
        f"/api/v1/operations/{operation_id}/start",
        {"operator_code": operator["code"]},
        token=operator_token,
        key=idempotency_key("start-op-10", suffix),
    )
    assert start["status"] == "in_progress"
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
            "inspector_code": inspector["code"],
        },
        token=inspector_token,
        key=idempotency_key("patrol", suffix),
    )
    assert patrol["result"] == "pass"
    first_clock = post_json(
        client,
        f"/api/v1/operations/{operation_id}/clock",
        {
            "good_qty": "5",
            "bad_qty": "0",
            "defects": [],
            "actual_materials": [{"material_code": steel["code"], "qty": "5", "lot_no": f"LOT-{suffix}"}],
            "operator_code": operator["code"],
        },
        token=operator_token,
        key=idempotency_key("clock-op-10", suffix),
    )
    assert first_clock["next_operation_id"] is not None

    next_operation_id = first_clock["next_operation_id"]
    second_start = post_json(
        client,
        f"/api/v1/operations/{next_operation_id}/start",
        {"operator_code": operator["code"]},
        token=operator_token,
        key=idempotency_key("start-op-20", suffix),
    )
    assert second_start["status"] == "in_progress"
    second_clock = post_json(
        client,
        f"/api/v1/operations/{next_operation_id}/clock",
        {
            "good_qty": "5",
            "bad_qty": "0",
            "defects": [],
            "actual_materials": [],
            "operator_code": operator["code"],
        },
        token=operator_token,
        key=idempotency_key("clock-op-20", suffix),
    )
    assert second_clock["work_order_status"] == "completed"

    final_quality = post_json(
        client,
        "/api/v1/quality/final",
        {
            "work_order_no": work_order_no,
            "sample_qty": "2",
            "pass_qty": "2",
            "fail_qty": "0",
            "result": "pass",
            "inspector_code": inspector["code"],
        },
        token=inspector_token,
        key=idempotency_key("final", suffix),
    )
    assert final_quality["inspect_type"] == "final"
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

    trace_response = client.get(
        f"/api/v1/work-orders/{work_order_no}/traceability",
        headers=auth_headers(planner_token),
    )
    assert trace_response.status_code == 200, trace_response.text
    trace = trace_response.json()
    assert trace["status"] == "closed"
    assert len(trace["clock_records"]) == 2
    assert trace["receipts"]
    assert any(event["event_type"] == "quality" for event in trace["timeline"])
