from decimal import Decimal

from pydantic import BaseModel


class WorkOrderDashboardRead(BaseModel):
    total: int
    draft: int
    pending: int
    scheduled: int
    in_progress: int
    completed: int
    ready_operations: int
    in_progress_operations: int
    actual_good_qty: Decimal
    actual_bad_qty: Decimal
