"""
HR Action Agent.
Performs HR tasks through chat by calling backend APIs as tools.
Never directly mutates the database.

Correct pattern:  Agent → Backend API → Service Layer → Database
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.llm import get_groq_llm
from app.services.ai.api_tools import (
    create_leave_request, update_leave_status, get_projects, create_ticket
)
from app.services.ai.permissions import check_permission, get_refusal_message

import json
import re

ACTION_SYSTEM_PROMPT = """You are the NovaWorks HR Action Assistant. You help employees perform HR tasks through chat.

Your job is to:
1. Understand the user's request
2. Extract the required parameters
3. Return a structured JSON action plan

AVAILABLE ACTIONS (based on user role: {role}):
{available_actions}

RESPONSE FORMAT - Return ONLY valid JSON:
{{
  "action": "<action_name>",
  "params": {{ ... }},
  "confirmation_message": "Brief description of what will be done"
}}

If the user's request doesn't match any available action, return:
{{
  "action": "none",
  "params": {{}},
  "confirmation_message": "I cannot perform this action. Here's what I can help with: [list relevant actions]"
}}

STRICT RULES:
1. Never fabricate actions that don't exist.
2. For leave dates, use YYYY-MM-DD format.
3. Leave types must be: SICK, CASUAL, or ANNUAL.
4. If parameters are missing, ask the user to provide them in the confirmation_message.

CURRENT USER:
- User ID: {user_id}
- Employee ID: {employee_id}
- Role: {role}
"""

ACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", ACTION_SYSTEM_PROMPT),
    ("human", "{message}")
])


def _get_available_actions(role: str) -> str:
    """List actions available for the given role."""
    actions = {
        "create_leave": "Apply for leave - params: leave_type (SICK/CASUAL/ANNUAL), start_date, end_date, reason",
        "view_projects": "View projects - no params needed",
        "create_ticket": "Raise a support ticket - params: title, description, category (IT/HR/FINANCE), priority (LOW/MEDIUM/HIGH)",
    }

    if role in ("MANAGER", "ADMIN"):
        actions["approve_leave"] = "Approve a leave request - params: leave_id"
        actions["reject_leave"] = "Reject a leave request - params: leave_id"

    return "\n".join(f"- {name}: {desc}" for name, desc in actions.items())


async def execute_hr_action(message: str, user_id: int, employee_id: int, role: str, access_token: str) -> dict:
    """
    Parse user intent, check permissions, and execute the HR action via backend API.
    
    Returns:
        dict with 'answer', 'action', and 'result' keys.
    """
    available_actions = _get_available_actions(role)
    llm = get_groq_llm(temperature=0.0)

    # Step 1: Extract action intent
    chain = ACTION_PROMPT | llm | StrOutputParser()
    raw_response = await chain.ainvoke({
        "role": role,
        "available_actions": available_actions,
        "user_id": user_id,
        "employee_id": employee_id,
        "message": message,
    })

    # Parse JSON from response
    try:
        # Clean markdown formatting if present
        cleaned = raw_response.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        action_plan = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {
            "answer": "I had trouble understanding your request. Could you please rephrase it? For example: 'Apply sick leave from May 6 to May 7 because I have fever.'",
            "action": None,
            "result": None
        }

    action = action_plan.get("action", "none")
    params = action_plan.get("params", {})
    confirmation = action_plan.get("confirmation_message", "")

    # Step 2: Permission check
    if action != "none" and not check_permission(role, action):
        return {
            "answer": get_refusal_message(action),
            "action": action,
            "result": {"blocked": True, "reason": "insufficient_permissions"}
        }

    # Step 3: Execute action via backend API
    if action == "create_leave":
        payload = {
            "leave_type": params.get("leave_type", "CASUAL"),
            "start_date": params.get("start_date"),
            "end_date": params.get("end_date"),
            "reason": params.get("reason", "Personal reason"),
        }
        if not payload["start_date"] or not payload["end_date"]:
            return {
                "answer": "I need the start date and end date for your leave request. Please specify them (e.g., 'from May 6 to May 7').",
                "action": action,
                "result": None
            }
        result = await create_leave_request(payload, access_token)
        if result["success"]:
            data = result["data"]
            return {
                "answer": f"✅ Your {payload['leave_type'].lower()} leave request from {payload['start_date']} to {payload['end_date']} has been submitted successfully. Status: Pending approval.",
                "action": action,
                "result": result
            }
        else:
            return {
                "answer": f"❌ Failed to create leave request: {result.get('error', 'Unknown error')}",
                "action": action,
                "result": result
            }

    elif action == "approve_leave":
        leave_id = params.get("leave_id")
        if not leave_id:
            return {
                "answer": "I need the leave request ID to approve. Please specify which leave request to approve.",
                "action": action,
                "result": None
            }
        result = await update_leave_status(int(leave_id), "APPROVED", access_token)
        if result["success"]:
            return {
                "answer": f"✅ Leave request #{leave_id} has been approved.",
                "action": action,
                "result": result
            }
        else:
            return {
                "answer": f"❌ Failed to approve leave request: {result.get('error', 'Unknown error')}",
                "action": action,
                "result": result
            }

    elif action == "reject_leave":
        leave_id = params.get("leave_id")
        if not leave_id:
            return {
                "answer": "I need the leave request ID to reject. Please specify which leave request to reject.",
                "action": action,
                "result": None
            }
        result = await update_leave_status(int(leave_id), "REJECTED", access_token)
        if result["success"]:
            return {
                "answer": f"✅ Leave request #{leave_id} has been rejected.",
                "action": action,
                "result": result
            }
        else:
            return {
                "answer": f"❌ Failed to reject leave request: {result.get('error', 'Unknown error')}",
                "action": action,
                "result": result
            }

    elif action == "view_projects":
        result = await get_projects(access_token)
        if result["success"]:
            projects = result["data"]
            if not projects:
                return {"answer": "No projects found.", "action": action, "result": result}
            project_list = "\n".join(
                f"- **{p['name']}**: {p.get('description', 'No description')} ({'Ongoing' if p.get('is_ongoing') else 'Completed'})"
                for p in projects
            )
            return {
                "answer": f"Here are the current projects:\n{project_list}",
                "action": action,
                "result": result
            }
        else:
            return {"answer": "Failed to fetch projects.", "action": action, "result": result}

    elif action == "create_ticket":
        payload = {
            "title": params.get("title") or params.get("subject"),
            "description": params.get("description") or message,
            "category": params.get("category", "IT").upper(),
            "priority": params.get("priority", "MEDIUM").upper(),
        }
        if not payload["title"]:
            return {
                "answer": "I need a title or subject for the ticket. What should I call it?",
                "action": action,
                "result": None
            }
        
        # Ensure category is valid
        if payload["category"] not in ["IT", "HR", "FINANCE"]:
            payload["category"] = "IT"
            
        result = await create_ticket(payload, access_token)
        if result["success"]:
            ticket = result["data"]
            return {
                "answer": f"✅ Support ticket created successfully!\n\n**Ticket ID**: #{ticket.get('id', 'N/A')}\n**Title**: {payload['title']}\n**Status**: {ticket.get('status', 'OPEN')}\n\nYou can track its progress in the 'My Tickets' section.",
                "action": action,
                "result": result
            }
        else:
            return {
                "answer": f"❌ Failed to create ticket: {result.get('error', 'Unknown error')}",
                "action": action,
                "result": result
            }

    else:
        return {
            "answer": confirmation or "I'm not sure how to help with that. I can help you apply for leave, view projects, or (if you're a manager) approve/reject leave requests.",
            "action": None,
            "result": None
        }
