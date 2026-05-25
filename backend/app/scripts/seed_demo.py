from __future__ import annotations

import argparse
import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor
from app.core.defaults import DEFAULT_OPERATOR_CODE, DEFAULT_PLANNER_CODE, DEFAULT_TENANT_ID
from app.db.session import AsyncSessionLocal, engine
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
)
from app.models.production import WorkOrder
from app.schemas.work_order import WorkOrderCreate
from app.services.work_order import confirm_work_order, create_work_order, schedule_work_order


async def upsert_by_code(
    session: AsyncSession,
    model: type[Any],
    code: str,
    values: dict[str, Any],
) -> Any:
    entity = await session.scalar(select(model).where(model.tenant_id == DEFAULT_TENANT_ID, model.code == code))
    if entity:
        for key, value in values.items():
            setattr(entity, key, value)
        entity.deleted_at = None
        return entity

    entity = model(tenant_id=DEFAULT_TENANT_ID, code=code, **values)
    session.add(entity)
    await session.flush()
    return entity


async def upsert_demo_bom(
    session: AsyncSession,
    product: Material,
    steel: Material,
    bearing: Material,
    box: Material,
) -> Bom:
    bom = await session.scalar(
        select(Bom).where(Bom.tenant_id == DEFAULT_TENANT_ID, Bom.material_id == product.id, Bom.version == "V1")
    )
    if not bom:
        bom = Bom(tenant_id=DEFAULT_TENANT_ID, material_id=product.id, version="V1")
        session.add(bom)
        await session.flush()

    bom.status = "active"
    bom.remark = "演示 BOM：单层展开，适合主流程验收"
    bom.deleted_at = None
    await session.execute(delete(BomLine).where(BomLine.bom_id == bom.id))
    session.add_all(
        [
            BomLine(
                tenant_id=DEFAULT_TENANT_ID,
                bom_id=bom.id,
                component_material_id=steel.id,
                line_no=10,
                qty_per=Decimal("1.200000"),
                loss_rate=Decimal("0.020000"),
                remark="主材",
            ),
            BomLine(
                tenant_id=DEFAULT_TENANT_ID,
                bom_id=bom.id,
                component_material_id=bearing.id,
                line_no=20,
                qty_per=Decimal("2.000000"),
                loss_rate=Decimal("0"),
                remark="标准件",
            ),
            BomLine(
                tenant_id=DEFAULT_TENANT_ID,
                bom_id=bom.id,
                component_material_id=box.id,
                line_no=30,
                qty_per=Decimal("1.000000"),
                loss_rate=Decimal("0"),
                remark="完工包装",
            ),
        ]
    )
    return bom


async def upsert_demo_routing(
    session: AsyncSession,
    product: Material,
    cnc: WorkCenter,
    deburr: WorkCenter,
    qc: WorkCenter,
) -> Routing:
    routing = await session.scalar(
        select(Routing).where(
            Routing.tenant_id == DEFAULT_TENANT_ID,
            Routing.material_id == product.id,
            Routing.version == "V1",
        )
    )
    if not routing:
        routing = Routing(tenant_id=DEFAULT_TENANT_ID, material_id=product.id, version="V1")
        session.add(routing)
        await session.flush()

    routing.status = "active"
    routing.remark = "演示工艺：CNC 加工 -> 去毛刺 -> 终检"
    routing.deleted_at = None
    await session.execute(delete(RoutingOperation).where(RoutingOperation.routing_id == routing.id))
    session.add_all(
        [
            RoutingOperation(
                tenant_id=DEFAULT_TENANT_ID,
                routing_id=routing.id,
                seq=10,
                operation_code="OP-CNC",
                operation_name="CNC 加工",
                work_center_id=cnc.id,
                setup_time_sec=600,
                unit_time_sec=180,
            ),
            RoutingOperation(
                tenant_id=DEFAULT_TENANT_ID,
                routing_id=routing.id,
                seq=20,
                operation_code="OP-DEBURR",
                operation_name="去毛刺",
                work_center_id=deburr.id,
                setup_time_sec=120,
                unit_time_sec=60,
            ),
            RoutingOperation(
                tenant_id=DEFAULT_TENANT_ID,
                routing_id=routing.id,
                seq=30,
                operation_code="OP-QC",
                operation_name="终检",
                work_center_id=qc.id,
                setup_time_sec=60,
                unit_time_sec=30,
            ),
        ]
    )
    return routing


async def seed_master_data(session: AsyncSession) -> None:
    async with session.begin():
        product = await upsert_by_code(
            session,
            Material,
            "P-AXLE-001",
            {
                "name": "电机轴组件",
                "spec": "EA-100",
                "unit": "pcs",
                "material_type": "product",
                "is_active": True,
                "allow_empty_bom": False,
                "remark": "演示成品",
            },
        )
        steel = await upsert_by_code(
            session,
            Material,
            "M-STEEL-001",
            {
                "name": "45# 圆钢",
                "spec": "D25",
                "unit": "kg",
                "material_type": "raw_material",
                "is_active": True,
                "allow_empty_bom": False,
                "remark": "演示主材",
            },
        )
        bearing = await upsert_by_code(
            session,
            Material,
            "M-BEARING-001",
            {
                "name": "轴承",
                "spec": "6203",
                "unit": "pcs",
                "material_type": "raw_material",
                "is_active": True,
                "allow_empty_bom": False,
                "remark": "演示标准件",
            },
        )
        box = await upsert_by_code(
            session,
            Material,
            "PCK-BOX-001",
            {
                "name": "包装纸箱",
                "spec": "A4",
                "unit": "pcs",
                "material_type": "packing",
                "is_active": True,
                "allow_empty_bom": False,
                "remark": "演示包装材料",
            },
        )
        cnc = await upsert_by_code(
            session,
            WorkCenter,
            "WC-CNC-01",
            {
                "name": "CNC 一号机",
                "work_center_type": "equipment",
                "location": "一车间",
                "is_active": True,
                "remark": "演示加工设备",
            },
        )
        deburr = await upsert_by_code(
            session,
            WorkCenter,
            "WC-DEBURR-01",
            {
                "name": "去毛刺工位",
                "work_center_type": "workstation",
                "location": "一车间",
                "is_active": True,
                "remark": "演示人工工位",
            },
        )
        qc = await upsert_by_code(
            session,
            WorkCenter,
            "WC-QC-01",
            {
                "name": "质检工位",
                "work_center_type": "inspection",
                "location": "一车间",
                "is_active": True,
                "remark": "演示质量工位",
            },
        )
        team = await upsert_by_code(
            session,
            Team,
            "TEAM-A",
            {
                "name": "A 班",
                "leader_name": "王班长",
                "is_active": True,
                "remark": "演示班组",
            },
        )
        await upsert_by_code(
            session,
            Worker,
            DEFAULT_PLANNER_CODE,
            {
                "name": "默认计划员",
                "worker_type": "planner",
                "team_id": team.id,
                "is_active": True,
                "remark": "系统默认计划员",
            },
        )
        await upsert_by_code(
            session,
            Worker,
            DEFAULT_OPERATOR_CODE,
            {
                "name": "默认操作员",
                "worker_type": "operator",
                "team_id": team.id,
                "is_active": True,
                "remark": "系统默认车间操作员",
            },
        )
        await upsert_by_code(
            session,
            Worker,
            "QC-001",
            {
                "name": "默认质检员",
                "worker_type": "inspector",
                "team_id": team.id,
                "is_active": True,
                "remark": "系统默认质检员",
            },
        )
        for code, name, category in [
            ("D-SCRATCH", "划伤", "外观"),
            ("D-DIMENSION", "尺寸超差", "尺寸"),
            ("D-BURR", "毛刺残留", "外观"),
        ]:
            await upsert_by_code(
                session,
                DefectReason,
                code,
                {
                    "name": name,
                    "category": category,
                    "is_active": True,
                    "remark": "演示不良原因",
                },
            )
        await upsert_demo_bom(session, product, steel, bearing, box)
        await upsert_demo_routing(session, product, cnc, deburr, qc)


async def ensure_demo_work_order(session: AsyncSession) -> tuple[str, str]:
    actor = Actor(tenant_id=DEFAULT_TENANT_ID, code=DEFAULT_PLANNER_CODE)
    existing = await session.scalar(
        select(WorkOrder)
        .where(
            WorkOrder.tenant_id == DEFAULT_TENANT_ID,
            WorkOrder.external_ref == "DEMO-SO-001",
            WorkOrder.deleted_at.is_(None),
        )
        .order_by(WorkOrder.created_at.desc())
    )
    if not existing:
        await session.rollback()
        response = await create_work_order(
            session,
            WorkOrderCreate(
                material_code="P-AXLE-001",
                quantity=Decimal("20"),
                due_date=date(2026, 6, 1),
                priority="high",
                source="manual",
                external_ref="DEMO-SO-001",
                customer_name="演示客户",
                remark="种子脚本创建的演示工单",
            ),
            actor,
            "seed-demo-work-order-v1",
        )
        work_order_no = response["work_order_no"]
        await confirm_work_order(session, work_order_no, actor)
        await schedule_work_order(session, work_order_no, actor)
        return work_order_no, "created"

    work_order_no = existing.work_order_no
    existing_status = existing.status
    await session.rollback()
    if existing_status == "draft":
        confirmed = await confirm_work_order(session, work_order_no, actor)
        existing_status = confirmed["status"]
    if existing_status == "pending":
        await schedule_work_order(session, work_order_no, actor)
        return work_order_no, "scheduled"
    return work_order_no, "existing"


async def run(skip_work_order: bool) -> None:
    async with AsyncSessionLocal() as session:
        await seed_master_data(session)

    work_order_result: tuple[str, str] | None = None
    if not skip_work_order:
        async with AsyncSessionLocal() as session:
            work_order_result = await ensure_demo_work_order(session)

    print("Demo master data is ready.")
    if work_order_result:
        work_order_no, status = work_order_result
        print(f"Demo work order {work_order_no} is {status}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Easy MES demo master data.")
    parser.add_argument(
        "--skip-work-order",
        action="store_true",
        help="Only seed master data, without creating or scheduling the demo work order.",
    )
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    try:
        await run(skip_work_order=args.skip_work_order)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
