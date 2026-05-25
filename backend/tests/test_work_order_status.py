from app.models.production import WorkOrder, WorkOrderOperation
from app.services.work_order import derive_work_order_status


def operation(status: str) -> WorkOrderOperation:
    return WorkOrderOperation(status=status)


def test_derive_work_order_status_prefers_running_operation() -> None:
    work_order = WorkOrder(status="paused")

    status = derive_work_order_status(work_order, [operation("paused"), operation("in_progress"), operation("ready")])

    assert status == "in_progress"


def test_derive_work_order_status_only_pauses_when_all_active_operations_are_paused() -> None:
    work_order = WorkOrder(status="in_progress")

    assert derive_work_order_status(work_order, [operation("paused"), operation("paused")]) == "paused"
    assert derive_work_order_status(work_order, [operation("paused"), operation("ready")]) == "scheduled"


def test_derive_work_order_status_marks_completed_when_all_operations_done() -> None:
    work_order = WorkOrder(status="in_progress")

    status = derive_work_order_status(work_order, [operation("done"), operation("done")])

    assert status == "completed"
