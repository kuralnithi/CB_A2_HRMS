"""
Backend API Tool wrappers for the HR Action Agent.
These functions call the existing FastAPI backend APIs with the user's auth token.

Architecture rule: Agent → Backend API → Service Layer → Database
(No direct DB writes from AI agents)
"""
import httpx
from app.core.config import settings

BASE_URL = f"http://localhost:8000{settings.API_V1_STR}"


async def create_leave_request(payload: dict, access_token: str) -> dict:
    """
    Calls POST /api/v1/leaves/ to create a leave request.
    
    payload keys: leave_type (SICK/CASUAL/ANNUAL), start_date, end_date, reason
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/leaves/",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.is_success:
            return {"success": True, "data": response.json()}
        
        # Handle cases where response might not be JSON
        try:
            error_detail = response.json().get("detail", "Failed to create leave request")
        except:
            error_detail = response.text or "Failed to create leave request"
            
        return {"success": False, "error": error_detail}


async def update_leave_status(leave_id: int, status: str, access_token: str) -> dict:
    """
    Calls PATCH /api/v1/leaves/{leave_id}?status={status} to approve/reject a leave.
    Only MANAGER and ADMIN roles can do this.
    """
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{BASE_URL}/leaves/{leave_id}",
            params={"status": status},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.is_success:
            return {"success": True, "data": response.json()}
            
        try:
            error_detail = response.json().get("detail", "Failed to update leave status")
        except:
            error_detail = response.text or "Failed to update leave status"
            
        return {"success": False, "error": error_detail}


async def approve_all_pending_leaves(access_token: str) -> dict:
    """
    Calls POST /api/v1/leaves/approve-all to approve all pending leaves.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/leaves/approve-all",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.is_success:
            return {"success": True, "data": response.json()}
            
        try:
            error_detail = response.json().get("detail", "Failed to bulk approve leaves")
        except:
            error_detail = response.text or "Failed to bulk approve leaves"
            
        return {"success": False, "error": error_detail}


async def get_projects(access_token: str) -> dict:
    """Calls GET /api/v1/projects/ to list all projects."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/projects/",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.is_success:
            return {"success": True, "data": response.json()}
        return {"success": False, "error": "Failed to fetch projects"}


async def create_ticket(payload: dict, access_token: str) -> dict:
    """
    Calls POST /api/v1/tickets/ to create a support ticket.
    
    payload keys: title, description, category (IT/HR/FINANCE), priority (LOW/MEDIUM/HIGH)
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/tickets/",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.is_success:
            return {"success": True, "data": response.json()}
            
        try:
            error_detail = response.json().get("detail", "Failed to create ticket")
        except:
            error_detail = response.text or "Failed to create ticket"
            
        return {"success": False, "error": error_detail}


async def update_ticket_status(ticket_id: int, new_status: str, access_token: str) -> dict:
    """
    Calls PATCH /api/v1/tickets/{ticket_id}/status to update a ticket's status.
    Only MANAGER and ADMIN can do this.
    
    new_status: OPEN, IN_PROGRESS, RESOLVED, CLOSED
    """
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{BASE_URL}/tickets/{ticket_id}/status",
            params={"new_status": new_status},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.is_success:
            return {"success": True, "data": response.json()}
            
        try:
            error_detail = response.json().get("detail", "Failed to update ticket status")
        except:
            error_detail = response.text or "Failed to update ticket status"
            
        return {"success": False, "error": error_detail}


async def close_all_open_tickets(ticket_ids: list, access_token: str) -> dict:
    """
    Closes multiple tickets by calling PATCH /api/v1/tickets/{id}/status for each.
    Only MANAGER and ADMIN can do this.
    """
    results = []
    success_count = 0
    for tid in ticket_ids:
        res = await update_ticket_status(int(tid), "CLOSED", access_token)
        results.append(res)
        if res.get("success"):
            success_count += 1
    return {
        "success": success_count > 0,
        "success_count": success_count,
        "total": len(ticket_ids),
        "data": results,
    }

