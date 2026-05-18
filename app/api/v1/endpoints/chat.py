"""
Chat API Endpoints.
POST /api/v1/chat/policy   → Policy RAG Assistant
POST /api/v1/chat/sql      → SQL Agent
POST /api/v1/chat/actions   → HR Task Automation Agent
POST /api/v1/chat/router    → Unified AI Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models.user import User
from app.models.hr import Employee
from app.api.v1.endpoints.auth import get_current_active_user
from app.services.ai.policy_rag import query_policy_rag
from app.services.ai.sql_agent import query_sql_agent
from app.services.ai.action_agent import execute_hr_action
from app.services.ai.router import route_query
from app.services.ai.audit import log_ai_interaction
from app.core import security

router = APIRouter()


# --- Schemas ---

class ChatRequest(BaseModel):
    message: str

class PolicySource(BaseModel):
    title: str
    category: str

class PolicyResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

class SQLResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

class ActionResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

class RouterResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# --- Helper ---

async def _get_employee_optional(db: AsyncSession, user: User) -> Employee | None:
    """Get the Employee record linked to the current user (returns None if not found)."""
    result = await db.execute(select(Employee).where(Employee.user_id == user.id))
    return result.scalars().first()


# --- Endpoints ---

@router.post("/policy", response_model=PolicyResponse)
async def chat_policy(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Policy RAG Assistant - answers HR policy questions using retrieved context."""
    try:
        result = await query_policy_rag(req.message)

        # Audit log
        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="POLICY_QA",
            tool_name="policy_rag",
            action_status="success",
        )

        return PolicyResponse(success=True, data=result)
    except Exception as e:
        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="POLICY_QA",
            tool_name="policy_rag",
            action_status="error",
        )
        return PolicyResponse(success=False, error=str(e))


@router.post("/sql", response_model=SQLResponse)
async def chat_sql(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """SQL Agent - converts natural language to safe, read-only SQL queries."""
    try:
        employee = await _get_employee_optional(db, current_user)
        result = await query_sql_agent(
            question=req.message,
            user_id=current_user.id,
            employee_id=employee.id if employee else None,
            role=current_user.role.value,
        )

        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="SQL_QUERY",
            tool_name="sql_agent",
            action_status="success" if result.get("rows") else "no_results",
            records_accessed=str(len(result.get("rows", []))),
        )

        return SQLResponse(success=True, data=result)
    except Exception as e:
        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="SQL_QUERY",
            tool_name="sql_agent",
            action_status="error",
        )
        return SQLResponse(success=False, error=str(e))


@router.post("/actions", response_model=ActionResponse)
async def chat_actions(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    token: str = Depends(security.oauth2_scheme),
):
    """HR Task Automation Agent - performs HR actions via backend API calls."""
    try:
        employee = await _get_employee_optional(db, current_user)
        result = await execute_hr_action(
            message=req.message,
            user_id=current_user.id,
            employee_id=employee.id if employee else None,
            role=current_user.role.value,
            access_token=token,
        )

        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="HR_ACTION",
            tool_name=result.get("action", "unknown"),
            action_status="success" if result.get("result") else "no_action",
        )

        return ActionResponse(success=True, data=result)
    except Exception as e:
        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="HR_ACTION",
            tool_name="action_agent",
            action_status="error",
        )
        return ActionResponse(success=False, error=str(e))


@router.post("/router", response_model=RouterResponse)
async def chat_router(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    token: str = Depends(security.oauth2_scheme),
):
    """Unified AI Router - classifies intent and routes to the correct sub-agent."""
    try:
        # Employee profile is optional — admin users may not have one
        employee = await _get_employee_optional(db, current_user)
        result = await route_query(
            message=req.message,
            user_id=current_user.id,
            employee_id=employee.id if employee else None,
            role=current_user.role.value,
            access_token=token,
        )

        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent=result.get("intent", "UNKNOWN"),
            tool_name="unified_router",
            action_status="success",
        )

        return RouterResponse(success=True, data=result)
    except Exception as e:
        import traceback
        print(f"[chat_router ERROR] {e}\n{traceback.format_exc()}")
        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="UNKNOWN",
            tool_name="unified_router",
            action_status="error",
        )
        return RouterResponse(success=False, error=str(e))
