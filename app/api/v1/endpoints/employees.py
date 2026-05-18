import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.db.session import get_db
from app.models.hr import Employee, Department, EmployeeProject, Project, LeaveRequest, LeaveStatusEnum
from app.models.user import User, RoleEnum
from app.api.v1.endpoints.auth import get_current_active_user
from app.core.security import get_password_hash

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class DepartmentResponse(BaseModel):
    id: int
    name: str
    class Config:
        orm_mode = True


class ProjectSummary(BaseModel):
    id: int
    name: str
    status: Optional[str]
    role_in_project: Optional[str]
    class Config:
        orm_mode = True


class EmployeeResponse(BaseModel):
    id: int
    user_id: Optional[int]
    name: str
    employee_code: Optional[str]
    designation: Optional[str]
    department_id: Optional[int]
    department_name: Optional[str]
    manager_id: Optional[int]
    manager_name: Optional[str]
    skills: Optional[str]
    certifications: Optional[str]
    employment_status: Optional[str]
    phone: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[date]
    date_of_joining: Optional[date]
    years_of_experience: Optional[float]
    work_location: Optional[str]
    allocation_percentage: Optional[float]
    is_billable: Optional[bool]
    profile_photo_url: Optional[str]
    # Admin-only
    current_salary_usd: Optional[float] = None
    hr_notes: Optional[str] = None

    class Config:
        orm_mode = True


class EmployeeCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "EMPLOYEE"
    designation: Optional[str] = None
    department_id: Optional[int] = None
    manager_id: Optional[int] = None
    skills: Optional[str] = None
    certifications: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_joining: Optional[date] = None
    work_location: Optional[str] = None
    employment_status: str = "ACTIVE"
    current_salary_usd: Optional[float] = None
    employee_code: Optional[str] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    department_id: Optional[int] = None
    manager_id: Optional[int] = None
    skills: Optional[str] = None
    certifications: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_joining: Optional[date] = None
    work_location: Optional[str] = None
    employment_status: Optional[str] = None
    current_salary_usd: Optional[float] = None
    hr_notes: Optional[str] = None
    allocation_percentage: Optional[float] = None
    is_billable: Optional[bool] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _enrich_employee(emp: Employee, db: AsyncSession, requester_role: str, requester_user_id: int) -> dict:
    """Build enriched employee dict with department/manager names."""
    result = {}
    for col in EmployeeResponse.__fields__:
        result[col] = getattr(emp, col, None)

    # Department name
    if emp.department_id:
        dept_res = await db.execute(select(Department).where(Department.id == emp.department_id))
        dept = dept_res.scalars().first()
        result["department_name"] = dept.name if dept else None
    else:
        result["department_name"] = None

    # Manager name
    if emp.manager_id:
        mgr_res = await db.execute(select(Employee).where(Employee.id == emp.manager_id))
        mgr = mgr_res.scalars().first()
        result["manager_name"] = mgr.name if mgr else None
    else:
        result["manager_name"] = None

    # Hide salary/hr_notes from non-admins viewing others
    if requester_role == RoleEnum.EMPLOYEE and emp.user_id != requester_user_id:
        result["current_salary_usd"] = None
        result["hr_notes"] = None
    if requester_role == RoleEnum.MANAGER:
        result["hr_notes"] = None

    return result


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/departments", response_model=List[DepartmentResponse])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Department))
    return result.scalars().all()


@router.get("/me", response_model=EmployeeResponse)
async def get_my_employee_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Fetch the current logged-in employee's full profile."""
    result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
    emp = result.scalars().first()
    if not emp:
        # Fallback for admin users who might not have an employee record
        if current_user.role == RoleEnum.ADMIN:
            return EmployeeResponse(
                id=0,
                user_id=current_user.id,
                name="Admin User",
                employee_code="ADMIN",
                designation="System Administrator",
                employment_status="ACTIVE"
            )
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    d = await _enrich_employee(emp, db, current_user.role, current_user.id)
    return EmployeeResponse(**d)


@router.post("/profile-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload and update profile photo for the current employee."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
    emp = result.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")

    # Ensure directory exists (redundant but safe)
    upload_dir = "static/uploads/profile_photos"
    os.makedirs(upload_dir, exist_ok=True)

    # Save file with unique name
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"profile_{emp.id}_{int(datetime.utcnow().timestamp())}{file_ext}"
    file_path = os.path.join(upload_dir, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
    
    # Update DB - Use relative URL for frontend
    photo_url = f"/static/uploads/profile_photos/{filename}"
    emp.profile_photo_url = photo_url
    await db.commit()
    
    return {"url": photo_url}


@router.get("/", response_model=List[EmployeeResponse])
async def list_employees(
    status: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == RoleEnum.EMPLOYEE:
        # Employee can only see themselves
        emp_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
        employees = emp_result.scalars().all()
    elif current_user.role == RoleEnum.MANAGER:
        # Manager sees their direct reports
        mgr_emp = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
        mgr = mgr_emp.scalars().first()
        if mgr:
            q = select(Employee).where(Employee.manager_id == mgr.id)
            emp_result = await db.execute(q)
            employees = emp_result.scalars().all()
        else:
            employees = []
    else:
        # Admin sees all
        q = select(Employee)
        if status:
            q = q.where(Employee.employment_status == status)
        if department_id:
            q = q.where(Employee.department_id == department_id)
        if search:
            q = q.where(Employee.name.ilike(f"%{search}%"))
        result = await db.execute(q)
        employees = result.scalars().all()

    enriched = []
    for emp in employees:
        d = await _enrich_employee(emp, db, current_user.role, current_user.id)
        enriched.append(EmployeeResponse(**d))
    return enriched


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    d = await _enrich_employee(emp, db, current_user.role, current_user.id)
    return EmployeeResponse(**d)


@router.post("/", response_model=EmployeeResponse, status_code=201)
async def create_employee(
    emp_in: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to create employees")

    result = await db.execute(select(User).where(User.email == emp_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    role_enum = RoleEnum(emp_in.role.upper()) if emp_in.role.upper() in RoleEnum._value2member_map_ else RoleEnum.EMPLOYEE
    db_user = User(
        email=emp_in.email,
        hashed_password=get_password_hash(emp_in.password),
        role=role_enum
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    db_employee = Employee(
        user_id=db_user.id,
        name=emp_in.name,
        designation=emp_in.designation,
        department_id=emp_in.department_id,
        manager_id=emp_in.manager_id,
        skills=emp_in.skills,
        certifications=emp_in.certifications,
        phone=emp_in.phone,
        gender=emp_in.gender,
        date_of_joining=emp_in.date_of_joining,
        work_location=emp_in.work_location,
        employment_status=emp_in.employment_status,
        current_salary_usd=emp_in.current_salary_usd,
        employee_code=emp_in.employee_code,
        is_billable=True,
        allocation_percentage=100.0,
    )
    db.add(db_employee)
    await db.commit()
    await db.refresh(db_employee)

    d = await _enrich_employee(db_employee, db, current_user.role, current_user.id)
    return EmployeeResponse(**d)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = data.dict(exclude_unset=True)
    # Manager cannot update salary/hr_notes
    if current_user.role == RoleEnum.MANAGER:
        update_data.pop("current_salary_usd", None)
        update_data.pop("hr_notes", None)

    for key, val in update_data.items():
        setattr(emp, key, val)
    emp.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(emp)

    d = await _enrich_employee(emp, db, current_user.role, current_user.id)
    return EmployeeResponse(**d)


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to delete employees")

    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    db_employee = result.scalars().first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    user_id = db_employee.user_id
    await db.delete(db_employee)

    if user_id:
        user_result = await db.execute(select(User).where(User.id == user_id))
        db_user = user_result.scalars().first()
        if db_user:
            await db.delete(db_user)

    await db.commit()
    return {"success": True, "message": "Employee deleted"}


@router.get("/{employee_id}/projects")
async def get_employee_projects(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(
        select(EmployeeProject, Project)
        .join(Project, EmployeeProject.project_id == Project.id)
        .where(EmployeeProject.employee_id == employee_id)
    )
    rows = result.all()
    return [
        {
            "project_id": proj.id,
            "project_name": proj.name,
            "status": proj.status,
            "role_in_project": ep.role_in_project,
            "is_active": ep.is_active,
            "allocation_percentage": ep.allocation_percentage,
        }
        for ep, proj in rows
    ]


@router.get("/{employee_id}/leave-summary")
async def get_employee_leave_summary(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    total = await db.execute(
        select(func.count(LeaveRequest.id)).where(LeaveRequest.employee_id == employee_id)
    )
    approved = await db.execute(
        select(func.count(LeaveRequest.id)).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveStatusEnum.APPROVED
        )
    )
    pending = await db.execute(
        select(func.count(LeaveRequest.id)).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveStatusEnum.PENDING
        )
    )
    total_val = total.scalar_one()
    approved_val = approved.scalar_one()
    pending_val = pending.scalar_one()
    return {
        "total": total_val,
        "approved": approved_val,
        "pending": pending_val,
        "remaining": max(0, 20 - approved_val),  # 20 total leaves per year
    }
