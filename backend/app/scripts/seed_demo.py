from __future__ import annotations

import argparse
import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor
from app.core.defaults import DEFAULT_OPERATOR_CODE, DEFAULT_PLANNER_CODE, DEFAULT_TENANT_ID
from app.core.security import hash_password
from app.db.session import dispose_engine, get_async_sessionmaker
from app.models.auth import RevokedToken, UserAccount
from app.models.master_data import (
    Bom,
    BomLine,
    DefectReason,
    Material,
    Routing,
    RoutingOperation,
    Team,
    WorkCenter,
    Worker,
    WorkerOperationSkill,
)
from app.models.production import (
    AuditLog,
    ClockRecord,
    DocumentSequence,
    IdempotencyKey,
    ProductionReceipt,
    QualityRecord,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderOperation,
)
from app.schemas.work_order import WorkOrderCreate, WorkOrderOperationAssignment, WorkOrderSchedule
from app.services.work_order import confirm_work_order, create_work_order, schedule_work_order


def planner_actor() -> Actor:
    return Actor(
        tenant_id=DEFAULT_TENANT_ID,
        code="planner",
        role="planner",
        display_name="Planner",
        worker_code=DEFAULT_PLANNER_CODE,
        worker_name="Default Planner",
    )


async def clear_default_tenant(session: AsyncSession) -> None:
    models = [
        IdempotencyKey,
        AuditLog,
        QualityRecord,
        ProductionReceipt,
        ClockRecord,
        RevokedToken,
        WorkOrderMaterial,
        WorkOrderOperation,
        WorkOrder,
        RoutingOperation,
        Routing,
        BomLine,
        Bom,
        UserAccount,
        WorkerOperationSkill,
        Worker,
        DefectReason,
        Team,
        WorkCenter,
        Material,
        DocumentSequence,
    ]
    for model in models:
        await session.execute(delete(model).where(model.tenant_id == DEFAULT_TENANT_ID))


def build_user(username: str, password: str, display_name: str, role: str, worker: Worker | None) -> UserAccount:
    return UserAccount(
        tenant_id=DEFAULT_TENANT_ID,
        username=username,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        worker_id=worker.id if worker else None,
        is_active=True,
        remark="MVP seed account",
    )


async def seed_master_data(session: AsyncSession) -> dict[str, Any]:
    product = Material(
        tenant_id=DEFAULT_TENANT_ID,
        code="P-MVP-001",
        name="MVP Product",
        spec="STD",
        unit="pcs",
        material_type="product",
        is_active=True,
        allow_empty_bom=False,
        remark="Seed product for the end-to-end MES flow.",
    )
    raw = Material(
        tenant_id=DEFAULT_TENANT_ID,
        code="M-MVP-RAW",
        name="MVP Raw Material",
        spec="RAW",
        unit="kg",
        material_type="raw_material",
        is_active=True,
        allow_empty_bom=False,
        remark="Seed raw material.",
    )
    session.add_all([product, raw])
    await session.flush()

    machining = WorkCenter(
        tenant_id=DEFAULT_TENANT_ID,
        code="WC-MACH-01",
        name="Machining Station",
        work_center_type="equipment",
        location="Line 1",
        is_active=True,
        remark="Seed machining work center.",
    )
    inspection = WorkCenter(
        tenant_id=DEFAULT_TENANT_ID,
        code="WC-QC-01",
        name="Inspection Station",
        work_center_type="inspection",
        location="Line 1",
        is_active=True,
        remark="Seed inspection work center.",
    )
    session.add_all([machining, inspection])
    await session.flush()

    team = Team(
        tenant_id=DEFAULT_TENANT_ID,
        code="TEAM-MVP",
        name="MVP Team",
        leader_name="Team Lead",
        is_active=True,
        remark="Seed team.",
    )
    session.add(team)
    await session.flush()

    planner = Worker(
        tenant_id=DEFAULT_TENANT_ID,
        code=DEFAULT_PLANNER_CODE,
        name="Default Planner",
        worker_type="planner",
        team_id=team.id,
        is_active=True,
        remark="Linked to planner account.",
    )
    operator = Worker(
        tenant_id=DEFAULT_TENANT_ID,
        code=DEFAULT_OPERATOR_CODE,
        name="Default Operator",
        worker_type="operator",
        team_id=team.id,
        is_active=True,
        remark="Linked to operator account.",
    )
    operator_two = Worker(
        tenant_id=DEFAULT_TENANT_ID,
        code="OP-002",
        name="Operator Two",
        worker_type="operator",
        team_id=team.id,
        is_active=True,
        remark="Used to verify task assignment isolation.",
    )
    inspector = Worker(
        tenant_id=DEFAULT_TENANT_ID,
        code="QC-001",
        name="Default Inspector",
        worker_type="inspector",
        team_id=team.id,
        is_active=True,
        remark="Linked to inspector account.",
    )
    session.add_all([planner, operator, operator_two, inspector])
    await session.flush()

    session.add_all(
        [
            build_user("admin", "admin123", "Admin", "admin", None),
            build_user("planner", "planner123", "Planner", "planner", planner),
            build_user("operator", "operator123", "Default Operator", "operator", operator),
            build_user("operator2", "operator123", "Operator Two", "operator", operator_two),
            build_user("inspector", "inspector123", "Inspector", "inspector", inspector),
        ]
    )

    defect_reason = DefectReason(
        tenant_id=DEFAULT_TENANT_ID,
        code="D-MVP-NG",
        name="MVP Defect",
        category="general",
        is_active=True,
        remark="Minimal defect reason for reporting validation.",
    )
    session.add(defect_reason)

    bom = Bom(
        tenant_id=DEFAULT_TENANT_ID,
        material_id=product.id,
        version="V1",
        status="active",
        remark="Minimal one-level BOM.",
    )
    bom.lines.append(
        BomLine(
            tenant_id=DEFAULT_TENANT_ID,
            component_material_id=raw.id,
            line_no=10,
            qty_per=Decimal("1.000000"),
            loss_rate=Decimal("0"),
            remark="One unit raw material per finished product.",
        )
    )
    session.add(bom)

    routing = Routing(
        tenant_id=DEFAULT_TENANT_ID,
        material_id=product.id,
        version="V1",
        status="active",
        remark="Minimal route: process then inspect.",
    )
    routing.operations.extend(
        [
            RoutingOperation(
                tenant_id=DEFAULT_TENANT_ID,
                seq=10,
                operation_code="OP-10",
                operation_name="Process",
                work_center_id=machining.id,
                setup_time_sec=0,
                unit_time_sec=30,
                is_active=True,
                remark="First operation.",
            ),
            RoutingOperation(
                tenant_id=DEFAULT_TENANT_ID,
                seq=20,
                operation_code="OP-20",
                operation_name="Final Inspect",
                work_center_id=inspection.id,
                setup_time_sec=0,
                unit_time_sec=10,
                is_active=True,
                remark="Second operation.",
            ),
        ]
    )
    session.add(routing)
    session.add_all(
        [
            WorkerOperationSkill(
                tenant_id=DEFAULT_TENANT_ID,
                worker_id=operator.id,
                operation_code="OP-10",
                operation_name_snapshot="Process",
                is_active=True,
                remark="Default operator can process.",
            ),
            WorkerOperationSkill(
                tenant_id=DEFAULT_TENANT_ID,
                worker_id=operator.id,
                operation_code="OP-20",
                operation_name_snapshot="Final Inspect",
                is_active=True,
                remark="Default operator can inspect in MVP demo.",
            ),
            WorkerOperationSkill(
                tenant_id=DEFAULT_TENANT_ID,
                worker_id=operator_two.id,
                operation_code="OP-10",
                operation_name_snapshot="Process",
                is_active=True,
                remark="Operator two can only run OP-10 in the MVP demo.",
            ),
        ]
    )

    return {
        "product": product,
        "raw": raw,
        "operator": operator,
        "operator_two": operator_two,
        "inspector": inspector,
    }


async def create_scheduled_work_order(
    session: AsyncSession,
    *,
    external_ref: str,
    quantity: Decimal,
    operator_code: str | None = None,
    operation_assignments: list[WorkOrderOperationAssignment] | None = None,
) -> str:
    actor = planner_actor()
    created = await create_work_order(
        session,
        WorkOrderCreate(
            material_code="P-MVP-001",
            quantity=quantity,
            due_date=date(2026, 6, 1),
            priority="high",
            source="manual",
            external_ref=external_ref,
            customer_name="MVP Customer",
            remark="Created by the minimal MVP seed.",
        ),
        actor,
        f"seed-{external_ref}-create",
    )
    work_order_no = created["work_order_no"]
    await confirm_work_order(session, work_order_no, actor, f"seed-{external_ref}-confirm")
    await schedule_work_order(
        session,
        work_order_no,
        actor,
        f"seed-{external_ref}-schedule",
        WorkOrderSchedule(operator_code=operator_code, operation_assignments=operation_assignments or []),
    )
    return work_order_no


async def seed_work_orders() -> list[str]:
    async_session_local = get_async_sessionmaker()
    async with async_session_local() as session:
        first = await create_scheduled_work_order(
            session,
            external_ref="SEED-MVP-001",
            quantity=Decimal("5"),
            operator_code=DEFAULT_OPERATOR_CODE,
        )
        second = await create_scheduled_work_order(
            session,
            external_ref="SEED-MVP-002",
            quantity=Decimal("3"),
            operation_assignments=[
                WorkOrderOperationAssignment(operation_seq=10, operator_code="OP-002"),
                WorkOrderOperationAssignment(operation_seq=20, operator_code=DEFAULT_OPERATOR_CODE),
            ],
        )
        return [first, second]


async def reset_default_tenant_data() -> None:
    async_session_local = get_async_sessionmaker()
    async with async_session_local() as session:
        async with session.begin():
            await clear_default_tenant(session)


async def seed_master_data_only() -> None:
    async_session_local = get_async_sessionmaker()
    async with async_session_local() as session:
        async with session.begin():
            await seed_master_data(session)


async def run(*, skip_work_orders: bool, reset_only: bool) -> None:
    await reset_default_tenant_data()
    if reset_only:
        print("Default tenant data has been reset.")
        return

    await seed_master_data_only()
    work_order_nos: list[str] = []
    if not skip_work_orders:
        work_order_nos = await seed_work_orders()

    print("Minimal MVP seed is ready.")
    print("Accounts:")
    print("  admin / admin123")
    print("  planner / planner123")
    print("  operator / operator123")
    print("  operator2 / operator123")
    print("  inspector / inspector123")
    print("Master data:")
    print("  product=P-MVP-001, raw=M-MVP-RAW, route=OP-10 -> OP-20")
    if work_order_nos:
        print("Scheduled work orders:")
        print(f"  {work_order_nos[0]} assigned to {DEFAULT_OPERATOR_CODE}")
        print(f"  {work_order_nos[1]} OP-10 assigned to OP-002, OP-20 assigned to {DEFAULT_OPERATOR_CODE}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset and seed a minimal Easy MES MVP dataset.")
    parser.add_argument(
        "--reset-only",
        action="store_true",
        help="Only clear the default tenant dataset, without recreating users, master data, or work orders.",
    )
    parser.add_argument(
        "--skip-work-orders",
        "--skip-work-order",
        action="store_true",
        dest="skip_work_orders",
        help="Only seed users and master data, without creating scheduled work orders.",
    )
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    try:
        await run(skip_work_orders=args.skip_work_orders, reset_only=args.reset_only)
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
