from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.db.session import get_db
from app.models.hr import Ticket, Employee
from app.models.user import User, RoleEnum
from app.api.v1.endpoints.auth import get_current_active_user

router = APIRouter()


class TicketCreate(BaseModel):
    title: str
    description: str
    priority: str = "MEDIUM"


class TicketResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    title: str
    description: str
    status: str
    priority: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _build(ticket: Ticket, emp_name: Optional[str] = None) -> dict:
    return {
        "id": ticket.id,
        "employee_id": ticket.employee_id,
        "employee_name": emp_name,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at,
    }


@router.get("/", response_model=List[TicketResponse])
async def list_tickets(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        q = select(Ticket, Employee).join(Employee, Ticket.employee_id == Employee.id)
        if status:
            q = q.where(Ticket.status == status)
        result = await db.execute(q.order_by(Ticket.id.desc()))
        rows = result.all()
        return [_build(t, emp.name) for t, emp in rows]
    else:
        emp_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
        emp = emp_result.scalars().first()
        if not emp:
            return []
        q = select(Ticket).where(Ticket.employee_id == emp.id)
        if status:
            q = q.where(Ticket.status == status)
        result = await db.execute(q.order_by(Ticket.id.desc()))
        tickets = result.scalars().all()
        return [_build(t, emp.name) for t in tickets]


@router.post("/", response_model=TicketResponse, status_code=201)
async def create_ticket(
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    emp_result = await db.execute(select(Employee).where(Employee.user_id == current_user.id))
    emp = emp_result.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee record not found for this user")

    ticket = Ticket(
        employee_id=emp.id,
        title=data.title,
        description=data.description,
        status="OPEN",
        priority=data.priority,
        created_at=datetime.utcnow(),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return _build(ticket, emp.name)


@router.patch("/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: int,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = new_status
    await db.commit()
    return {"success": True, "ticket_id": ticket_id, "status": new_status}
