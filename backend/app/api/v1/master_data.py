from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Actor, get_default_actor
from app.db.session import get_db_session
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
from app.schemas.master_data import (
    BomCreate,
    BomRead,
    BomUpdate,
    DefectReasonCreate,
    DefectReasonRead,
    DefectReasonUpdate,
    MaterialCreate,
    MaterialRead,
    MaterialUpdate,
    OperationSkillOptionRead,
    RoutingCreate,
    RoutingRead,
    RoutingUpdate,
    TeamCreate,
    TeamRead,
    TeamUpdate,
    WorkCenterCreate,
    WorkCenterRead,
    WorkCenterUpdate,
    WorkerCreate,
    WorkerOperationSkillRead,
    WorkerOperationSkillUpdate,
    WorkerRead,
    WorkerUpdate,
)
from app.services.audit import write_audit_log

router = APIRouter(tags=["master-data"])


def utcnow() -> datetime:
    return datetime.now(UTC)


async def ensure_exists(
    session: AsyncSession,
    model: type,
    entity_id: UUID,
    tenant_id: UUID,
    message: str,
) -> Any:
    entity = await session.get(model, entity_id)
    if not entity or entity.tenant_id != tenant_id or entity.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return entity


async def list_entities(
    session: AsyncSession,
    model: type,
    read_schema: type,
    actor: Actor,
    *,
    keyword: str | None,
    is_active: bool | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    filters = [model.tenant_id == actor.tenant_id, model.deleted_at.is_(None)]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(model.code.ilike(pattern) | model.name.ilike(pattern))
    if is_active is not None and hasattr(model, "is_active"):
        filters.append(model.is_active == is_active)

    total = await session.scalar(select(func.count()).select_from(model).where(*filters))
    result = await session.scalars(
        select(model).where(*filters).order_by(model.created_at.desc()).limit(limit).offset(offset)
    )
    return {
        "total": total or 0,
        "items": [read_schema.model_validate(entity).model_dump(mode="json") for entity in list(result)],
    }


async def get_entity(session: AsyncSession, model: type, entity_id: UUID, actor: Actor) -> Any:
    entity = await session.get(model, entity_id)
    if not entity or entity.tenant_id != actor.tenant_id or entity.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    return entity


async def commit_with_integrity_handling(session: AsyncSession, duplicate_message: str) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=duplicate_message) from exc


async def flush_with_integrity_handling(session: AsyncSession, duplicate_message: str) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=duplicate_message) from exc


def apply_update(entity: Any, payload: Any) -> None:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, key, value)


ENTITY_AUDIT_FIELDS: dict[type, tuple[str, ...]] = {
    Material: ("code", "name", "spec", "unit", "material_type", "is_active", "allow_empty_bom", "remark"),
    WorkCenter: ("code", "name", "work_center_type", "location", "is_active", "remark"),
    Team: ("code", "name", "leader_name", "is_active", "remark"),
    Worker: ("code", "name", "worker_type", "team_id", "is_active", "remark"),
    DefectReason: ("code", "name", "category", "is_active", "remark"),
}


def encode_audit_value(value: Any) -> Any:
    return jsonable_encoder(value, custom_encoder={Decimal: str, UUID: str})


def entity_snapshot(entity: Any, fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    selected_fields = fields or ENTITY_AUDIT_FIELDS[type(entity)]
    return {field: encode_audit_value(getattr(entity, field)) for field in selected_fields}


def audit_create_detail(entity: Any, fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    return {"after": entity_snapshot(entity, fields)}


def audit_delete_detail(entity: Any, deleted_at: datetime, fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    return {"before": entity_snapshot(entity, fields), "deleted_at": encode_audit_value(deleted_at)}


def audit_update_detail(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes = {
        key: {"from": before.get(key), "to": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }
    return {"before": before, "after": after, "changes": changes}


def skill_snapshot(skills: list[WorkerOperationSkill]) -> list[dict[str, Any]]:
    return [
        {
            "operation_code": skill.operation_code,
            "operation_name": skill.operation_name_snapshot,
            "is_active": skill.is_active,
        }
        for skill in sorted(skills, key=lambda item: item.operation_code)
        if skill.deleted_at is None
    ]


async def active_operation_options(session: AsyncSession, tenant_id: UUID) -> dict[str, str]:
    rows = list(
        await session.scalars(
            select(RoutingOperation).where(
                RoutingOperation.tenant_id == tenant_id,
                RoutingOperation.deleted_at.is_(None),
                RoutingOperation.is_active.is_(True),
            )
        )
    )
    options: dict[str, str] = {}
    for row in sorted(rows, key=lambda item: (item.operation_code, item.seq)):
        options.setdefault(row.operation_code, row.operation_name)
    return options


def bom_snapshot(bom: Bom) -> dict[str, Any]:
    return {
        **entity_snapshot(bom, ("material_id", "version", "status", "remark")),
        "lines": [
            {
                "component_material_id": encode_audit_value(line.component_material_id),
                "line_no": line.line_no,
                "qty_per": encode_audit_value(line.qty_per),
                "loss_rate": encode_audit_value(line.loss_rate),
                "remark": line.remark,
            }
            for line in sorted(bom.lines, key=lambda item: item.line_no)
        ],
    }


def routing_snapshot(routing: Routing) -> dict[str, Any]:
    return {
        **entity_snapshot(routing, ("material_id", "version", "status", "remark")),
        "operations": [
            {
                "seq": operation.seq,
                "operation_code": operation.operation_code,
                "operation_name": operation.operation_name,
                "work_center_id": encode_audit_value(operation.work_center_id),
                "setup_time_sec": operation.setup_time_sec,
                "unit_time_sec": operation.unit_time_sec,
                "is_active": operation.is_active,
                "remark": operation.remark,
            }
            for operation in sorted(routing.operations, key=lambda item: item.seq)
        ],
    }


@router.get("/materials", response_model=dict)
async def list_materials(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    keyword: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await list_entities(
        db,
        Material,
        MaterialRead,
        actor,
        keyword=keyword,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.post("/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    payload: MaterialCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Material:
    material = Material(tenant_id=actor.tenant_id, **payload.model_dump())
    db.add(material)
    await flush_with_integrity_handling(db, "物料编码已存在")
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="material",
        entity_id=material.id,
        action="create",
        detail=audit_create_detail(material),
    )
    await commit_with_integrity_handling(db, "物料编码已存在")
    await db.refresh(material)
    return material


@router.get("/materials/{material_id}", response_model=MaterialRead)
async def get_material(
    material_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Material:
    return await get_entity(db, Material, material_id, actor)


@router.patch("/materials/{material_id}", response_model=MaterialRead)
async def update_material(
    material_id: UUID,
    payload: MaterialUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Material:
    material = await get_entity(db, Material, material_id, actor)
    before = entity_snapshot(material)
    apply_update(material, payload)
    after = entity_snapshot(material)
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="material",
        entity_id=material.id,
        action="update",
        detail=audit_update_detail(before, after),
    )
    await commit_with_integrity_handling(db, "物料编码已存在")
    await db.refresh(material)
    return material


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> None:
    material = await get_entity(db, Material, material_id, actor)
    deleted_at = utcnow()
    detail = audit_delete_detail(material, deleted_at)
    material.deleted_at = deleted_at
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="material",
        entity_id=material.id,
        action="delete",
        detail=detail,
    )
    await db.commit()


@router.get("/work-centers", response_model=dict)
async def list_work_centers(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    keyword: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await list_entities(
        db, WorkCenter, WorkCenterRead, actor, keyword=keyword, is_active=is_active, limit=limit, offset=offset
    )


@router.post("/work-centers", response_model=WorkCenterRead, status_code=status.HTTP_201_CREATED)
async def create_work_center(
    payload: WorkCenterCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> WorkCenter:
    entity = WorkCenter(tenant_id=actor.tenant_id, **payload.model_dump())
    db.add(entity)
    await flush_with_integrity_handling(db, "工位编码已存在")
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="work_center",
        entity_id=entity.id,
        action="create",
        detail=audit_create_detail(entity),
    )
    await commit_with_integrity_handling(db, "工位编码已存在")
    await db.refresh(entity)
    return entity


@router.get("/work-centers/{work_center_id}", response_model=WorkCenterRead)
async def get_work_center(
    work_center_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> WorkCenter:
    return await get_entity(db, WorkCenter, work_center_id, actor)


@router.patch("/work-centers/{work_center_id}", response_model=WorkCenterRead)
async def update_work_center(
    work_center_id: UUID,
    payload: WorkCenterUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> WorkCenter:
    entity = await get_entity(db, WorkCenter, work_center_id, actor)
    before = entity_snapshot(entity)
    apply_update(entity, payload)
    after = entity_snapshot(entity)
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="work_center",
        entity_id=entity.id,
        action="update",
        detail=audit_update_detail(before, after),
    )
    await commit_with_integrity_handling(db, "工位编码已存在")
    await db.refresh(entity)
    return entity


@router.delete("/work-centers/{work_center_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_center(
    work_center_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> None:
    entity = await get_entity(db, WorkCenter, work_center_id, actor)
    deleted_at = utcnow()
    detail = audit_delete_detail(entity, deleted_at)
    entity.deleted_at = deleted_at
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="work_center",
        entity_id=entity.id,
        action="delete",
        detail=detail,
    )
    await db.commit()


@router.get("/teams", response_model=dict)
async def list_teams(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    keyword: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await list_entities(
        db, Team, TeamRead, actor, keyword=keyword, is_active=is_active, limit=limit, offset=offset
    )


@router.post("/teams", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Team:
    entity = Team(tenant_id=actor.tenant_id, **payload.model_dump())
    db.add(entity)
    await flush_with_integrity_handling(db, "班组编码已存在")
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="team",
        entity_id=entity.id,
        action="create",
        detail=audit_create_detail(entity),
    )
    await commit_with_integrity_handling(db, "班组编码已存在")
    await db.refresh(entity)
    return entity


@router.patch("/teams/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Team:
    entity = await get_entity(db, Team, team_id, actor)
    before = entity_snapshot(entity)
    apply_update(entity, payload)
    after = entity_snapshot(entity)
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="team",
        entity_id=entity.id,
        action="update",
        detail=audit_update_detail(before, after),
    )
    await commit_with_integrity_handling(db, "班组编码已存在")
    await db.refresh(entity)
    return entity


@router.get("/teams/{team_id}", response_model=TeamRead)
async def get_team(
    team_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Team:
    return await get_entity(db, Team, team_id, actor)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> None:
    entity = await get_entity(db, Team, team_id, actor)
    deleted_at = utcnow()
    detail = audit_delete_detail(entity, deleted_at)
    entity.deleted_at = deleted_at
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="team",
        entity_id=entity.id,
        action="delete",
        detail=detail,
    )
    await db.commit()


@router.get("/workers", response_model=dict)
async def list_workers(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    keyword: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await list_entities(
        db, Worker, WorkerRead, actor, keyword=keyword, is_active=is_active, limit=limit, offset=offset
    )


@router.post("/workers", response_model=WorkerRead, status_code=status.HTTP_201_CREATED)
async def create_worker(
    payload: WorkerCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Worker:
    if payload.team_id:
        await ensure_exists(db, Team, payload.team_id, actor.tenant_id, "班组不存在")
    entity = Worker(tenant_id=actor.tenant_id, **payload.model_dump())
    db.add(entity)
    await flush_with_integrity_handling(db, "人员编码已存在")
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="worker",
        entity_id=entity.id,
        action="create",
        detail=audit_create_detail(entity),
    )
    await commit_with_integrity_handling(db, "人员编码已存在")
    await db.refresh(entity)
    return entity


@router.patch("/workers/{worker_id}", response_model=WorkerRead)
async def update_worker(
    worker_id: UUID,
    payload: WorkerUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Worker:
    entity = await get_entity(db, Worker, worker_id, actor)
    if payload.team_id:
        await ensure_exists(db, Team, payload.team_id, actor.tenant_id, "班组不存在")
    before = entity_snapshot(entity)
    apply_update(entity, payload)
    after = entity_snapshot(entity)
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="worker",
        entity_id=entity.id,
        action="update",
        detail=audit_update_detail(before, after),
    )
    await commit_with_integrity_handling(db, "人员编码已存在")
    await db.refresh(entity)
    return entity


@router.get("/workers/{worker_id}", response_model=WorkerRead)
async def get_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Worker:
    return await get_entity(db, Worker, worker_id, actor)


@router.get("/operation-skill-options", response_model=list[OperationSkillOptionRead])
async def list_operation_skill_options(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> list[dict[str, str]]:
    options = await active_operation_options(db, actor.tenant_id)
    return [
        {"operation_code": operation_code, "operation_name": operation_name}
        for operation_code, operation_name in sorted(options.items())
    ]


@router.get("/workers/{worker_id}/operation-skills", response_model=list[WorkerOperationSkillRead])
async def list_worker_operation_skills(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> list[dict[str, Any]]:
    worker = await get_entity(db, Worker, worker_id, actor)
    rows = list(
        await db.scalars(
            select(WorkerOperationSkill)
            .where(
                WorkerOperationSkill.tenant_id == actor.tenant_id,
                WorkerOperationSkill.worker_id == worker.id,
                WorkerOperationSkill.deleted_at.is_(None),
                WorkerOperationSkill.is_active.is_(True),
            )
            .order_by(WorkerOperationSkill.operation_code)
        )
    )
    return [
        WorkerOperationSkillRead(
            id=row.id,
            tenant_id=row.tenant_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
            worker_id=row.worker_id,
            operation_code=row.operation_code,
            operation_name=row.operation_name_snapshot,
            is_active=row.is_active,
            remark=row.remark,
        ).model_dump(mode="json")
        for row in rows
    ]


@router.put("/workers/{worker_id}/operation-skills", response_model=list[WorkerOperationSkillRead])
async def update_worker_operation_skills(
    worker_id: UUID,
    payload: WorkerOperationSkillUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> list[dict[str, Any]]:
    worker = await get_entity(db, Worker, worker_id, actor)
    if worker.worker_type != "operator":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有操作员需要配置可做工序")

    options = await active_operation_options(db, actor.tenant_id)
    requested_codes = list(dict.fromkeys(item.strip() for item in payload.operation_codes if item.strip()))
    unknown_codes = [code for code in requested_codes if code not in options]
    if unknown_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNKNOWN_OPERATION_SKILL", "message": f"工序编码不存在: {', '.join(unknown_codes)}"},
        )

    existing = list(
        await db.scalars(
            select(WorkerOperationSkill)
            .where(
                WorkerOperationSkill.tenant_id == actor.tenant_id,
                WorkerOperationSkill.worker_id == worker.id,
                WorkerOperationSkill.deleted_at.is_(None),
            )
            .with_for_update()
        )
    )
    before = skill_snapshot(existing)
    existing_by_code = {item.operation_code: item for item in existing}
    requested_set = set(requested_codes)

    for code, skill in existing_by_code.items():
        skill.is_active = code in requested_set
        if code in options:
            skill.operation_name_snapshot = options[code]

    for code in requested_codes:
        if code in existing_by_code:
            continue
        db.add(
            WorkerOperationSkill(
                tenant_id=actor.tenant_id,
                worker_id=worker.id,
                operation_code=code,
                operation_name_snapshot=options[code],
                is_active=True,
            )
        )

    await db.flush()
    updated = list(
        await db.scalars(
            select(WorkerOperationSkill)
            .where(
                WorkerOperationSkill.tenant_id == actor.tenant_id,
                WorkerOperationSkill.worker_id == worker.id,
                WorkerOperationSkill.deleted_at.is_(None),
            )
            .order_by(WorkerOperationSkill.operation_code)
        )
    )
    after = skill_snapshot(updated)
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="worker_operation_skill",
        entity_id=worker.id,
        action="update",
        detail={
            "worker_code": worker.code,
            "worker_name": worker.name,
            **audit_update_detail({"skills": before}, {"skills": after}),
        },
    )
    await db.commit()
    return [
        WorkerOperationSkillRead(
            id=row.id,
            tenant_id=row.tenant_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
            worker_id=row.worker_id,
            operation_code=row.operation_code,
            operation_name=row.operation_name_snapshot,
            is_active=row.is_active,
            remark=row.remark,
        ).model_dump(mode="json")
        for row in updated
        if row.is_active
    ]


@router.delete("/workers/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> None:
    entity = await get_entity(db, Worker, worker_id, actor)
    deleted_at = utcnow()
    detail = audit_delete_detail(entity, deleted_at)
    entity.deleted_at = deleted_at
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="worker",
        entity_id=entity.id,
        action="delete",
        detail=detail,
    )
    await db.commit()


@router.get("/defect-reasons", response_model=dict)
async def list_defect_reasons(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    keyword: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await list_entities(
        db,
        DefectReason,
        DefectReasonRead,
        actor,
        keyword=keyword,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.post("/defect-reasons", response_model=DefectReasonRead, status_code=status.HTTP_201_CREATED)
async def create_defect_reason(
    payload: DefectReasonCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> DefectReason:
    entity = DefectReason(tenant_id=actor.tenant_id, **payload.model_dump())
    db.add(entity)
    await flush_with_integrity_handling(db, "不良原因编码已存在")
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="defect_reason",
        entity_id=entity.id,
        action="create",
        detail=audit_create_detail(entity),
    )
    await commit_with_integrity_handling(db, "不良原因编码已存在")
    await db.refresh(entity)
    return entity


@router.patch("/defect-reasons/{reason_id}", response_model=DefectReasonRead)
async def update_defect_reason(
    reason_id: UUID,
    payload: DefectReasonUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> DefectReason:
    entity = await get_entity(db, DefectReason, reason_id, actor)
    before = entity_snapshot(entity)
    apply_update(entity, payload)
    after = entity_snapshot(entity)
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="defect_reason",
        entity_id=entity.id,
        action="update",
        detail=audit_update_detail(before, after),
    )
    await commit_with_integrity_handling(db, "不良原因编码已存在")
    await db.refresh(entity)
    return entity


@router.get("/defect-reasons/{reason_id}", response_model=DefectReasonRead)
async def get_defect_reason(
    reason_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> DefectReason:
    return await get_entity(db, DefectReason, reason_id, actor)


@router.delete("/defect-reasons/{reason_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_defect_reason(
    reason_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> None:
    entity = await get_entity(db, DefectReason, reason_id, actor)
    deleted_at = utcnow()
    detail = audit_delete_detail(entity, deleted_at)
    entity.deleted_at = deleted_at
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="defect_reason",
        entity_id=entity.id,
        action="delete",
        detail=detail,
    )
    await db.commit()


@router.post("/boms", response_model=BomRead, status_code=status.HTTP_201_CREATED)
async def create_bom(
    payload: BomCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Bom:
    await ensure_exists(db, Material, payload.material_id, actor.tenant_id, "物料不存在")
    bom = Bom(
        tenant_id=actor.tenant_id,
        material_id=payload.material_id,
        version=payload.version,
        status=payload.status,
        remark=payload.remark,
    )
    for line in payload.lines:
        await ensure_exists(db, Material, line.component_material_id, actor.tenant_id, "子件物料不存在")
        bom.lines.append(BomLine(tenant_id=actor.tenant_id, **line.model_dump()))
    db.add(bom)
    await flush_with_integrity_handling(db, "该物料的 BOM 版本已存在")
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="bom",
        entity_id=bom.id,
        action="create",
        detail={"after": bom_snapshot(bom)},
    )
    await commit_with_integrity_handling(db, "该物料的 BOM 版本已存在")
    return await get_bom(bom.id, db, actor)


@router.get("/boms", response_model=dict)
async def list_boms(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    material_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    filters = [Bom.tenant_id == actor.tenant_id, Bom.deleted_at.is_(None)]
    if material_id:
        filters.append(Bom.material_id == material_id)
    if status_filter:
        filters.append(Bom.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(Bom).where(*filters))
    result = await db.scalars(
        select(Bom)
        .options(selectinload(Bom.lines).selectinload(BomLine.component_material))
        .where(*filters)
        .order_by(Bom.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "total": total or 0,
        "items": [BomRead.model_validate(entity).model_dump(mode="json") for entity in list(result)],
    }


@router.get("/boms/{bom_id}", response_model=BomRead)
async def get_bom(
    bom_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Bom:
    result = await db.scalars(
        select(Bom)
        .options(selectinload(Bom.lines).selectinload(BomLine.component_material))
        .where(Bom.id == bom_id, Bom.tenant_id == actor.tenant_id, Bom.deleted_at.is_(None))
    )
    bom = result.first()
    if not bom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM 不存在")
    return bom


@router.patch("/boms/{bom_id}", response_model=BomRead)
async def update_bom(
    bom_id: UUID,
    payload: BomUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Bom:
    bom = await get_bom(bom_id, db, actor)
    before = bom_snapshot(bom)
    data = payload.model_dump(exclude_unset=True)
    lines = data.pop("lines", None)
    for key, value in data.items():
        setattr(bom, key, value)
    if lines is not None:
        bom.lines.clear()
        for line in lines:
            await ensure_exists(db, Material, line["component_material_id"], actor.tenant_id, "子件物料不存在")
            bom.lines.append(BomLine(tenant_id=actor.tenant_id, **line))
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="bom",
        entity_id=bom.id,
        action="update",
        detail=audit_update_detail(before, bom_snapshot(bom)),
    )
    await commit_with_integrity_handling(db, "该物料的 BOM 版本已存在")
    return await get_bom(bom.id, db, actor)


@router.delete("/boms/{bom_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bom(
    bom_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> None:
    bom = await get_bom(bom_id, db, actor)
    deleted_at = utcnow()
    detail = {"before": bom_snapshot(bom), "deleted_at": encode_audit_value(deleted_at)}
    bom.deleted_at = deleted_at
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="bom",
        entity_id=bom.id,
        action="delete",
        detail=detail,
    )
    await db.commit()


@router.post("/routings", response_model=RoutingRead, status_code=status.HTTP_201_CREATED)
async def create_routing(
    payload: RoutingCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Routing:
    await ensure_exists(db, Material, payload.material_id, actor.tenant_id, "物料不存在")
    routing = Routing(
        tenant_id=actor.tenant_id,
        material_id=payload.material_id,
        version=payload.version,
        status=payload.status,
        remark=payload.remark,
    )
    for operation in payload.operations:
        await ensure_exists(db, WorkCenter, operation.work_center_id, actor.tenant_id, "工位不存在")
        routing.operations.append(RoutingOperation(tenant_id=actor.tenant_id, **operation.model_dump()))
    db.add(routing)
    await flush_with_integrity_handling(db, "该物料的工艺路线版本已存在")
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="routing",
        entity_id=routing.id,
        action="create",
        detail={"after": routing_snapshot(routing)},
    )
    await commit_with_integrity_handling(db, "该物料的工艺路线版本已存在")
    return await get_routing(routing.id, db, actor)


@router.get("/routings", response_model=dict)
async def list_routings(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    material_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    filters = [Routing.tenant_id == actor.tenant_id, Routing.deleted_at.is_(None)]
    if material_id:
        filters.append(Routing.material_id == material_id)
    if status_filter:
        filters.append(Routing.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(Routing).where(*filters))
    result = await db.scalars(
        select(Routing)
        .options(selectinload(Routing.operations).selectinload(RoutingOperation.work_center))
        .where(*filters)
        .order_by(Routing.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "total": total or 0,
        "items": [RoutingRead.model_validate(entity).model_dump(mode="json") for entity in list(result)],
    }


@router.get("/routings/{routing_id}", response_model=RoutingRead)
async def get_routing(
    routing_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Routing:
    result = await db.scalars(
        select(Routing)
        .options(selectinload(Routing.operations).selectinload(RoutingOperation.work_center))
        .where(Routing.id == routing_id, Routing.tenant_id == actor.tenant_id, Routing.deleted_at.is_(None))
    )
    routing = result.first()
    if not routing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工艺路线不存在")
    return routing


@router.patch("/routings/{routing_id}", response_model=RoutingRead)
async def update_routing(
    routing_id: UUID,
    payload: RoutingUpdate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> Routing:
    routing = await get_routing(routing_id, db, actor)
    before = routing_snapshot(routing)
    data = payload.model_dump(exclude_unset=True)
    operations = data.pop("operations", None)
    for key, value in data.items():
        setattr(routing, key, value)
    if operations is not None:
        routing.operations.clear()
        for operation in operations:
            await ensure_exists(db, WorkCenter, operation["work_center_id"], actor.tenant_id, "工位不存在")
            routing.operations.append(RoutingOperation(tenant_id=actor.tenant_id, **operation))
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="routing",
        entity_id=routing.id,
        action="update",
        detail=audit_update_detail(before, routing_snapshot(routing)),
    )
    await commit_with_integrity_handling(db, "该物料的工艺路线版本已存在")
    return await get_routing(routing.id, db, actor)


@router.delete("/routings/{routing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routing(
    routing_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> None:
    routing = await get_routing(routing_id, db, actor)
    deleted_at = utcnow()
    detail = {"before": routing_snapshot(routing), "deleted_at": encode_audit_value(deleted_at)}
    routing.deleted_at = deleted_at
    await write_audit_log(
        db,
        tenant_id=actor.tenant_id,
        actor_code=actor.code,
        entity_type="routing",
        entity_id=routing.id,
        action="delete",
        detail=detail,
    )
    await db.commit()
