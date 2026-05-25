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


def post_json(client: TestClient, url: str, payload: dict, *, key: str | None = None) -> dict:
    headers = {"Idempotency-Key": key} if key else {}
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code in {200, 201}, response.text
    return response.json()


def test_mes_main_flow_from_master_data_to_traceability() -> None:
    suffix = uuid4().hex[:8].upper()
    with TestClient(app) as client:
        run_mes_main_flow(client, suffix)


def run_mes_main_flow(client: TestClient, suffix: str) -> None:
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
    )
    cnc = post_json(
        client,
        "/api/v1/work-centers",
        {
            "code": f"WC-E2E-CNC-{suffix}",
            "name": "端到端 CNC",
            "work_center_type": "equipment",
        },
    )
    qc = post_json(
        client,
        "/api/v1/work-centers",
        {
            "code": f"WC-E2E-QC-{suffix}",
            "name": "端到端质检",
            "work_center_type": "inspection",
        },
    )
    team = post_json(
        client,
        "/api/v1/teams",
        {
            "code": f"TEAM-E2E-{suffix}",
            "name": "端到端班组",
        },
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
    )
    post_json(
        client,
        "/api/v1/defect-reasons",
        {
            "code": f"D-E2E-{suffix}",
            "name": "端到端尺寸超差",
            "category": "尺寸",
        },
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
        key=idempotency_key("create-wo", suffix),
    )
    assert work_order["status"] == "draft"

    work_order_no = work_order["work_order_no"]
    confirmed = post_json(client, f"/api/v1/work-orders/{work_order_no}/confirm", {})
    assert confirmed["status"] == "pending"
    kitting = post_json(client, f"/api/v1/work-orders/{work_order_no}/kitting-check", {})
    assert kitting["is_complete"] is True
    scheduled = post_json(client, f"/api/v1/work-orders/{work_order_no}/schedule", {})
    assert scheduled["status"] == "scheduled"

    operation_id = scheduled["operations"][0]["id"]
    start = post_json(
        client,
        f"/api/v1/operations/{operation_id}/start",
        {"operator_code": operator["code"]},
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
        key=idempotency_key("clock-op-10", suffix),
    )
    assert first_clock["next_operation_id"] is not None

    next_operation_id = first_clock["next_operation_id"]
    second_start = post_json(
        client,
        f"/api/v1/operations/{next_operation_id}/start",
        {"operator_code": operator["code"]},
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
        key=idempotency_key("receipt", suffix),
    )
    assert receipt["work_order"]["status"] == "closed"

    trace_response = client.get(f"/api/v1/work-orders/{work_order_no}/traceability")
    assert trace_response.status_code == 200, trace_response.text
    trace = trace_response.json()
    assert trace["status"] == "closed"
    assert len(trace["clock_records"]) == 2
    assert trace["receipts"]
    assert any(event["event_type"] == "quality" for event in trace["timeline"])
