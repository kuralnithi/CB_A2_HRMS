from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.db.session import get_db
from app.models.hr import LeaveRequest, LeaveTypeEnum, LeaveStatusEnum, Employee
from app.models.user import User, RoleEnum
from app.api.v1.endpoints.auth import get_current_active_user

router = APIRouter()


class LeaveRequestCreate(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    reason: str


class LeaveRequestResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    leave_type: str
    start_date: date
    end_date: date
    reason: str
    status: str
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _build_response(leave: LeaveRequest, emp_name: Optional[str] = None) -> dict:
    d = {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "employee_name": emp_name,
        "leave_type": leave.leave_type.value if hasattr(leave.leave_type, 'value') else str(leave.leave_type),
        "start_date": leave.start_date,
        "end_date": leave.end_date,
        "reason": leave.reason,
        "status": leave.status.value if hasattr(leave.status, 'value') else str(leave.status),
        "reviewed_at": leave.reviewed_at,
    }
    return d


@router.post("/", response_model=LeaveRequestResponse, status_code=201)
async def create_leave_request(
    leave: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Get the employee record for current user
    emp_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
    emp = emp_result.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee record not found for this user")

    # Validate dates
    if leave.end_date < leave.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")

    db_leave = LeaveRequest(
        employee_id=emp.id,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        status=LeaveStatusEnum.PENDING,
        created_at=datetime.utcnow()
    )
    db.add(db_leave)
    await db.commit()
    await db.refresh(db_leave)
    return _build_response(db_leave, emp.name)


@router.patch("/{leave_id}")
async def update_leave_status(
    leave_id: int,
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.MANAGER, RoleEnum.ADMIN]:
        raise HTTPException(status_code=403, detail="Only managers and admins can review leave requests")

    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id))
    db_leave = result.scalars().first()
    if not db_leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    db_leave.status = status
    db_leave.reviewed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(db_leave)

    # Get employee name
    emp_result = await db.execute(select(Employee).where(Employee.id == db_leave.employee_id))
    emp = emp_result.scalars().first()
    return _build_response(db_leave, emp.name if emp else None)


@router.post("/approve-all")
async def approve_all_pending_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.MANAGER, RoleEnum.ADMIN]:
        raise HTTPException(status_code=403, detail="Only managers and admins can approve leave requests")

    if current_user.role == RoleEnum.ADMIN:
        result = await db.execute(select(LeaveRequest).where(LeaveRequest.status == LeaveStatusEnum.PENDING))
    else:
        mgr_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
        mgr = mgr_result.scalars().first()
        if not mgr:
            return {"success": True, "count": 0}

        team_result = await db.execute(
            select(Employee.id).where(Employee.manager_id == mgr.id)
        )
        team_ids = [r[0] for r in team_result.all()]
        if not team_ids:
            return {"success": True, "count": 0}

        result = await db.execute(
            select(LeaveRequest).where(
                LeaveRequest.status == LeaveStatusEnum.PENDING,
                LeaveRequest.employee_id.in_(team_ids)
            )
        )

    leaves = result.scalars().all()
    count = len(leaves)
    for leave in leaves:
        leave.status = LeaveStatusEnum.APPROVED
        leave.reviewed_at = datetime.utcnow()

    await db.commit()
    return {"success": True, "count": count}


@router.get("/", response_model=List[LeaveRequestResponse])
async def list_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == RoleEnum.ADMIN:
        result = await db.execute(
            select(LeaveRequest, Employee)
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .order_by(LeaveRequest.id.desc())
        )
        rows = result.all()
        return [_build_response(lr, emp.name) for lr, emp in rows]

    elif current_user.role == RoleEnum.MANAGER:
        mgr_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
        mgr = mgr_result.scalars().first()
        if not mgr:
            return []

        team_result = await db.execute(
            select(Employee.id).where(Employee.manager_id == mgr.id)
        )
        team_ids = [r[0] for r in team_result.all()]
        allowed_ids = team_ids + [mgr.id]

        result = await db.execute(
            select(LeaveRequest, Employee)
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .where(LeaveRequest.employee_id.in_(allowed_ids))
            .order_by(LeaveRequest.id.desc())
        )
        rows = result.all()
        return [_build_response(lr, emp.name) for lr, emp in rows]

    else:
        # Employee: own leaves only
        emp_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
        emp = emp_result.scalars().first()
        if not emp:
            return []

        result = await db.execute(
            select(LeaveRequest)
            .where(LeaveRequest.employee_id == emp.id)
            .order_by(LeaveRequest.id.desc())
        )
        leaves = result.scalars().all()
        return [_build_response(lr, emp.name) for lr in leaves]
