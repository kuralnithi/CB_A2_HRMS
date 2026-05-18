from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.db.session import get_db
from app.models.hr import (
    Project, EmployeeProject, Employee,
    ProjectStatusEnum, ProjectPriorityEnum, RiskLevelEnum, BillingTypeEnum
)
from app.models.user import User, RoleEnum
from app.api.v1.endpoints.auth import get_current_active_user

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TeamMemberResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    role_in_project: Optional[str]
    allocation_percentage: Optional[float]
    is_billable: Optional[bool]
    is_active: Optional[bool]

    class Config:
        orm_mode = True


class ProjectResponse(BaseModel):
    id: int
    name: str
    project_code: Optional[str]
    client_name: Optional[str]
    description: Optional[str]
    project_type: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    risk_level: Optional[str]
    start_date: Optional[date]
    deadline: Optional[date]
    budget_usd: Optional[float]
    estimated_cost: Optional[float]
    actual_cost: Optional[float]
    billing_type: Optional[str]
    tech_stack: Optional[str]
    repo_url: Optional[str]
    notes: Optional[str]
    is_ongoing: Optional[bool]
    is_deleted: Optional[bool]
    is_archived: Optional[bool]
    created_at: Optional[datetime]
    team_size: Optional[int] = 0

    class Config:
        orm_mode = True


class ProjectDetailResponse(ProjectResponse):
    members: List[TeamMemberResponse] = []


class ProjectCreate(BaseModel):
    name: str
    project_code: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: str = "PLANNING"
    priority: str = "MEDIUM"
    risk_level: Optional[str] = None
    start_date: Optional[date] = None
    deadline: Optional[date] = None
    budget_usd: Optional[float] = None
    estimated_cost: Optional[float] = None
    billing_type: Optional[str] = None
    tech_stack: Optional[str] = None
    repo_url: Optional[str] = None
    notes: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    project_code: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    risk_level: Optional[str] = None
    start_date: Optional[date] = None
    deadline: Optional[date] = None
    budget_usd: Optional[float] = None
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    billing_type: Optional[str] = None
    tech_stack: Optional[str] = None
    repo_url: Optional[str] = None
    notes: Optional[str] = None
    actual_completion_date: Optional[date] = None


class AssignMemberRequest(BaseModel):
    employee_id: int
    role_in_project: str = "Developer"
    allocation_percentage: float = 100.0
    is_billable: bool = True


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Base query
    if current_user.role in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        q = select(Project).where(Project.is_deleted == False)
    else:
        # Employee sees only their projects
        emp_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
        emp = emp_result.scalars().first()
        if not emp:
            return []
        q = (
            select(Project)
            .join(EmployeeProject, Project.id == EmployeeProject.project_id)
            .where(EmployeeProject.employee_id == emp.id, Project.is_deleted == False)
        )

    # Apply Filters
    if status:
        q = q.where(Project.status == status)
    if priority:
        q = q.where(Project.priority == priority)
    if search:
        q = q.where(Project.name.ilike(f"%{search}%"))

    result = await db.execute(q)
    projects = result.scalars().all()

    # Annotate with team_size
    for p in projects:
        cnt = await db.execute(
            select(func.count(EmployeeProject.id)).where(
                EmployeeProject.project_id == p.id,
                EmployeeProject.is_active == True
            )
        )
        p.team_size = cnt.scalar_one()

    return projects


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can create projects")

    proj = Project(**data.dict())
    proj.is_ongoing = data.status in ("PLANNING", "ONGOING")
    proj.is_deleted = False
    proj.is_archived = False
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    proj.team_size = 0
    return proj


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    proj = result.scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get members with employee name
    members_result = await db.execute(
        select(EmployeeProject, Employee)
        .join(Employee, EmployeeProject.employee_id == Employee.id)
        .where(EmployeeProject.project_id == project_id, EmployeeProject.is_active == True)
    )
    members_data = members_result.all()

    members_list = []
    for ep, emp in members_data:
        members_list.append(TeamMemberResponse(
            id=ep.id,
            employee_id=ep.employee_id,
            employee_name=emp.name,
            role_in_project=ep.role_in_project,
            allocation_percentage=ep.allocation_percentage,
            is_billable=ep.is_billable,
            is_active=ep.is_active,
        ))

    proj_dict = {c.name: getattr(proj, c.name) for c in proj.__table__.columns}
    proj_dict["members"] = members_list
    proj_dict["team_size"] = len(members_list)
    return proj_dict


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = data.dict(exclude_unset=True)
    for key, val in update_data.items():
        setattr(proj, key, val)
    proj.updated_at = datetime.utcnow()
    if "status" in update_data:
        proj.is_ongoing = update_data["status"] in ("PLANNING", "ONGOING")

    await db.commit()
    await db.refresh(proj)
    proj.team_size = 0
    return proj


@router.patch("/{project_id}/status")
async def change_project_status(
    project_id: int,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    proj.status = new_status
    proj.is_ongoing = new_status in ("PLANNING", "ONGOING")
    if new_status == "COMPLETED":
        proj.actual_completion_date = datetime.utcnow().date()
    await db.commit()
    return {"success": True, "status": new_status}


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can delete projects")

    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    proj.is_deleted = True
    await db.commit()
    return {"success": True, "message": "Project archived (soft deleted)"}


@router.post("/{project_id}/members", status_code=201)
async def assign_member(
    project_id: int,
    data: AssignMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check employee exists
    emp_result = await db.execute(select(Employee).where(Employee.id == data.employee_id))
    emp = emp_result.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Check if already assigned
    existing = await db.execute(
        select(EmployeeProject).where(
            EmployeeProject.project_id == project_id,
            EmployeeProject.employee_id == data.employee_id,
            EmployeeProject.is_active == True
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Employee already assigned to this project")

    ep = EmployeeProject(
        project_id=project_id,
        employee_id=data.employee_id,
        role_in_project=data.role_in_project,
        allocation_percentage=data.allocation_percentage,
        is_billable=data.is_billable,
        is_active=True,
        assigned_at=datetime.utcnow()
    )
    db.add(ep)
    await db.commit()
    return {"success": True, "message": f"Employee assigned as {data.role_in_project}"}


@router.delete("/{project_id}/members/{employee_id}")
async def remove_member(
    project_id: int,
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(EmployeeProject).where(
            EmployeeProject.project_id == project_id,
            EmployeeProject.employee_id == employee_id,
            EmployeeProject.is_active == True
        )
    )
    ep = result.scalars().first()
    if not ep:
        raise HTTPException(status_code=404, detail="Assignment not found")

    ep.is_active = False
    ep.removed_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "message": "Employee removed from project"}
