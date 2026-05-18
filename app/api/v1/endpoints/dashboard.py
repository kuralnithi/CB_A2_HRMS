from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.db.session import get_db
from app.models.user import User, RoleEnum
from app.models.hr import (
    Employee, LeaveRequest, Project, EmployeeProject, Ticket, Announcement,
    LeaveStatusEnum, ProjectStatusEnum, EmploymentStatusEnum
)
from app.api.v1.endpoints.auth import get_current_active_user
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class AdminDashboardStats(BaseModel):
    # Employee
    total_employees: int
    active_employees: int
    bench_employees: int
    notice_period_employees: int
    # Projects
    total_projects: int
    ongoing_projects: int
    completed_projects: int
    delayed_projects: int
    on_hold_projects: int
    # HR
    pending_leaves: int
    open_tickets: int
    total_announcements: int


class ManagerDashboardStats(BaseModel):
    team_size: int
    total_projects: int
    ongoing_projects: int
    pending_leaves: int
    open_tickets: int


class EmployeeDashboardStats(BaseModel):
    my_projects: int
    ongoing_projects: int
    pending_leaves: int
    leave_balance: int
    open_tickets: int


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == RoleEnum.ADMIN:
        return await _admin_stats(db)
    elif current_user.role == RoleEnum.MANAGER:
        return await _manager_stats(db, current_user)
    else:
        return await _employee_stats(db, current_user)


async def _admin_stats(db: AsyncSession) -> dict:
    total_emp = (await db.execute(select(func.count(Employee.id)))).scalar_one()
    active_emp = (await db.execute(
        select(func.count(Employee.id)).where(Employee.employment_status == EmploymentStatusEnum.ACTIVE)
    )).scalar_one()
    bench_emp = (await db.execute(
        select(func.count(Employee.id)).where(Employee.employment_status == EmploymentStatusEnum.BENCH)
    )).scalar_one()
    notice_emp = (await db.execute(
        select(func.count(Employee.id)).where(Employee.employment_status == EmploymentStatusEnum.NOTICE_PERIOD)
    )).scalar_one()

    total_proj = (await db.execute(
        select(func.count(Project.id)).where(Project.is_deleted == False)
    )).scalar_one()
    ongoing_proj = (await db.execute(
        select(func.count(Project.id)).where(Project.status == ProjectStatusEnum.ONGOING, Project.is_deleted == False)
    )).scalar_one()
    completed_proj = (await db.execute(
        select(func.count(Project.id)).where(Project.status == ProjectStatusEnum.COMPLETED, Project.is_deleted == False)
    )).scalar_one()
    delayed_proj = (await db.execute(
        select(func.count(Project.id)).where(Project.status == ProjectStatusEnum.DELAYED, Project.is_deleted == False)
    )).scalar_one()
    on_hold_proj = (await db.execute(
        select(func.count(Project.id)).where(Project.status == ProjectStatusEnum.ON_HOLD, Project.is_deleted == False)
    )).scalar_one()

    pending_leaves = (await db.execute(
        select(func.count(LeaveRequest.id)).where(LeaveRequest.status == LeaveStatusEnum.PENDING)
    )).scalar_one()
    open_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.status == "OPEN")
    )).scalar_one()
    announcements = (await db.execute(select(func.count(Announcement.id)))).scalar_one()

    return {
        "role": "ADMIN",
        "total_employees": total_emp,
        "active_employees": active_emp,
        "bench_employees": bench_emp,
        "notice_period_employees": notice_emp,
        "total_projects": total_proj,
        "ongoing_projects": ongoing_proj,
        "completed_projects": completed_proj,
        "delayed_projects": delayed_proj,
        "on_hold_projects": on_hold_proj,
        "pending_leaves": pending_leaves,
        "open_tickets": open_tickets,
        "total_announcements": announcements,
    }


async def _manager_stats(db: AsyncSession, current_user: User) -> dict:
    mgr_emp = (await db.execute(
        select(Employee).where(Employee.user_id == current_user.id)
    )).scalars().first()

    team_size = 0
    pending_leaves = 0
    if mgr_emp:
        team_size = (await db.execute(
            select(func.count(Employee.id)).where(Employee.manager_id == mgr_emp.id)
        )).scalar_one()

        # Get team employee ids for leave count
        team_emp_ids_result = await db.execute(
            select(Employee.id).where(Employee.manager_id == mgr_emp.id)
        )
        team_ids = [r[0] for r in team_emp_ids_result.all()]
        if team_ids:
            pending_leaves = (await db.execute(
                select(func.count(LeaveRequest.id)).where(
                    LeaveRequest.employee_id.in_(team_ids),
                    LeaveRequest.status == LeaveStatusEnum.PENDING
                )
            )).scalar_one()

    total_proj = (await db.execute(
        select(func.count(Project.id)).where(Project.is_deleted == False)
    )).scalar_one()
    ongoing_proj = (await db.execute(
        select(func.count(Project.id)).where(Project.status == ProjectStatusEnum.ONGOING, Project.is_deleted == False)
    )).scalar_one()
    open_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.status == "OPEN")
    )).scalar_one()

    return {
        "role": "MANAGER",
        "team_size": team_size,
        "total_projects": total_proj,
        "ongoing_projects": ongoing_proj,
        "pending_leaves": pending_leaves,
        "open_tickets": open_tickets,
    }


async def _employee_stats(db: AsyncSession, current_user: User) -> dict:
    emp_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
    emp = emp_result.scalars().first()

    my_projects = 0
    ongoing_projects = 0
    pending_leaves = 0
    open_tickets = 0

    if emp:
        my_projects = (await db.execute(
            select(func.count(EmployeeProject.id)).where(
                EmployeeProject.employee_id == emp.id,
                EmployeeProject.is_active == True
            )
        )).scalar_one()

        ongoing_projects = (await db.execute(
            select(func.count(EmployeeProject.id))
            .join(Project, EmployeeProject.project_id == Project.id)
            .where(
                EmployeeProject.employee_id == emp.id,
                EmployeeProject.is_active == True,
                Project.status == ProjectStatusEnum.ONGOING
            )
        )).scalar_one()

        pending_leaves = (await db.execute(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.employee_id == emp.id,
                LeaveRequest.status == LeaveStatusEnum.PENDING
            )
        )).scalar_one()
        approved_leaves = (await db.execute(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.employee_id == emp.id,
                LeaveRequest.status == LeaveStatusEnum.APPROVED
            )
        )).scalar_one()

        open_tickets = (await db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.employee_id == emp.id,
                Ticket.status == "OPEN"
            )
        )).scalar_one()

    return {
        "role": "EMPLOYEE",
        "my_projects": my_projects,
        "ongoing_projects": ongoing_projects,
        "pending_leaves": pending_leaves,
        "leave_balance": max(0, 20 - (approved_leaves if emp else 0)),
        "open_tickets": open_tickets,
    }
