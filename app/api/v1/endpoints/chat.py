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
from app.models.ai import ChatSession, ChatMessage
from app.api.v1.endpoints.auth import get_current_active_user
from app.services.ai.policy_rag import query_policy_rag
from app.services.ai.sql_agent import query_sql_agent
from app.services.ai.action_agent import execute_hr_action
from app.services.ai.router import route_query
from app.services.ai.audit import log_ai_interaction
from app.core import security
from datetime import datetime
import uuid

router = APIRouter()


# --- Schemas ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: Optional[List[dict]] = None

class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    intent: Optional[str] = None
    sources: Optional[list] = None
    sql: Optional[str] = None
    rows: Optional[list] = None
    action_result: Optional[dict] = None
    dev_metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[ChatMessageResponse]] = None

    model_config = {"from_attributes": True}

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


# --- Session Endpoints ---

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    exclude_session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all chat sessions for the current user, auto-deleting unused empty sessions."""
    # Find all sessions with 0 messages (excluding the active one to prevent deleting active New Chat)
    empty_sessions_query = (
        select(ChatSession)
        .where(
            ChatSession.user_id == current_user.id,
            ~select(ChatMessage).where(ChatMessage.session_id == ChatSession.id).exists()
        )
    )
    if exclude_session_id:
        empty_sessions_query = empty_sessions_query.where(ChatSession.id != exclude_session_id)

    empty_sessions_result = await db.execute(empty_sessions_query)
    empty_sessions = empty_sessions_result.scalars().all()

    # Delete the empty sessions
    for s in empty_sessions:
        await db.delete(s)
    if empty_sessions:
        await db.commit()

    # Fetch and return the remaining valid sessions
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at, "updated_at": s.updated_at, "messages": []} for s in sessions]

@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific chat session with its messages."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Need to load messages explicitly since it's an async session
    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()
    
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": messages
    }

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new chat session."""
    session = ChatSession(
        user_id=current_user.id,
        title="New Conversation"
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": []
    }

@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a chat session."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    await db.delete(session)
    await db.commit()
    return {"success": True}


# --- Helper ---


async def _get_employee_optional(db: AsyncSession, user: User) -> Employee | None:
    """Get the Employee record linked to the current user (returns None if not found)."""
    result = await db.execute(select(Employee).where(Employee.user_id == user.id))
    return result.scalars().first()

async def _save_chat_messages(db: AsyncSession, session_id: str, user_msg: str, asst_msg_data: dict):
    if not session_id:
        return
    
    # 1. Save User Message
    user_chat = ChatMessage(
        session_id=session_id,
        role="user",
        content=user_msg
    )
    db.add(user_chat)
    
    # 2. Save Assistant Message
    asst_chat = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=asst_msg_data.get("content", ""),
        intent=asst_msg_data.get("intent"),
        sources=asst_msg_data.get("sources"),
        sql=asst_msg_data.get("sql"),
        rows=asst_msg_data.get("rows"),
        action_result=asst_msg_data.get("action_result"),
        dev_metadata=asst_msg_data.get("dev_metadata"),
    )
    db.add(asst_chat)
    
    # 3. Update Session
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalars().first()
    if session:
        session.updated_at = datetime.utcnow()
        # Optionally update title based on first user message if it's "New Conversation"
        if session.title == "New Conversation":
            session.title = user_msg[:50] + ("..." if len(user_msg) > 50 else "")
            
    await db.commit()


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

        await _save_chat_messages(
            db=db,
            session_id=req.session_id,
            user_msg=req.message,
            asst_msg_data={"content": result.get("answer", ""), "intent": "POLICY_QA", "sources": result.get("sources")}
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

        await _save_chat_messages(
            db=db,
            session_id=req.session_id,
            user_msg=req.message,
            asst_msg_data={
                "content": result.get("answer", ""),
                "intent": "SQL_QUERY",
                "sql": result.get("sql"),
                "rows": result.get("rows"),
                "dev_metadata": result.get("dev_metadata")
            }
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
    """HR Task Automation Agent - executes actions like apply_leave, view_projects, etc."""
    try:
        employee = await _get_employee_optional(db, current_user)
        result = await execute_hr_action(
            message=req.message,
            user_id=current_user.id,
            employee_id=employee.id if employee else None,
            role=current_user.role.value,
            access_token=token,
        )

        action_name = result.get("action", "unknown")
        success = result.get("success", False)

        await log_ai_interaction(
            db=db,
            user_id=current_user.id,
            role=current_user.role.value,
            message=req.message,
            intent="HR_ACTION",
            tool_name=f"action_{action_name}",
            action_status="success" if success else "failed",
        )

        await _save_chat_messages(
            db=db,
            session_id=req.session_id,
            user_msg=req.message,
            asst_msg_data={"content": result.get("answer", ""), "intent": "HR_ACTION", "action_result": {"action": action_name, "success": success}}
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
async def route_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    token: str = Depends(security.oauth2_scheme),
):
    """Unified API that automatically routes user requests to Policy, SQL, or Actions."""
    try:
        employee = await _get_employee_optional(db, current_user)

        result = await route_query(
            message=req.message,
            user_id=current_user.id,
            employee_id=employee.id if employee else None,
            role=current_user.role.value,
            access_token=token,
            history=req.history
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

        await _save_chat_messages(
            db=db,
            session_id=req.session_id,
            user_msg=req.message,
            asst_msg_data={
                "content": result.get("data", {}).get("answer", ""),
                "intent": result.get("intent", "UNKNOWN"),
                "action_result": result.get("data", {}).get("action_result", None),
                "rows": result.get("data", {}).get("rows"),
                "sql": result.get("data", {}).get("sql"),
                "dev_metadata": result.get("dev_metadata")
            }
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
