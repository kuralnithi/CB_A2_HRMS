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
    create_leave_request, update_leave_status, get_projects, create_ticket,
    update_ticket_status, close_all_open_tickets
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

CONVERSATION HISTORY (use this to extract IDs and context for follow-up actions):
{history_context}

IMPORTANT: If the user refers to "this leave", "that request", "it", or similar pronouns, look in the CONVERSATION HISTORY above to find the relevant leave ID, ticket ID, or other IDs. Extract them automatically — do NOT ask the user for IDs that are already visible in the history.

RESPONSE FORMAT - Return ONLY valid JSON:
{{
  "action": "<action_name>",
  "params": {{ ... }},
  "confirmation_message": "Brief description of what will be done"
}}

If the user asks to perform MULTIPLE actions (e.g., approve one leave and reject another), you can return a JSON array of these objects:
[
  {{ "action": "approve_leave", "params": {{"leave_ids": [10]}} }},
  {{ "action": "reject_leave", "params": {{"leave_ids": [11]}} }}
]

If the user's request doesn't match any available action, return:
{{
  "action": "none",
  "params": {{}},
  "confirmation_message": "I cannot perform this action. Here's what I can help with: [list relevant capabilities]"
}}

STRICT RULES:
1. Never fabricate actions that don't exist.
2. For leave dates, use YYYY-MM-DD format.
3. Leave types must be: SICK, CASUAL, or ANNUAL.
4. If parameters are missing AND cannot be inferred from conversation history, ask the user to provide them in the confirmation_message.
5. Always prefer to extract IDs from conversation history before asking the user.

CURRENT USER:
- User ID: {user_id}
- Employee ID: {employee_id}
- Role: {role}
- Current Date/Time: {current_time}
"""

ACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", ACTION_SYSTEM_PROMPT),
    ("human", "{message}")
])


def _build_history_context(history: list) -> str:
    """Build a concise context string from recent chat history for the action agent."""
    if not history:
        return "No previous conversation."
    
    context_parts = []
    for msg in history[-6:]:  # Last 6 messages
        role_label = "User" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "")
        # Truncate long assistant messages but keep IDs visible
        if role_label == "Assistant" and len(content) > 500:
            content = content[:500] + "..."
        # CRITICAL: Escape curly braces so LangChain's ChatPromptTemplate doesn't
        # misinterpret JSON data (e.g., {"id": 5}) as template variables.
        content = content.replace("{", "{{").replace("}", "}}")
        context_parts.append(f"{role_label}: {content}")
    
    return "\n".join(context_parts)


def _get_available_actions(role: str) -> str:
    """List actions available for the given role."""
    actions = {
        "create_leave": "Apply for leave - params: leave_type (SICK/CASUAL/ANNUAL), start_date, end_date, reason",
        "view_projects": "View projects - no params needed",
        "create_ticket": "Raise a support ticket - params: title, description, category (IT/HR/FINANCE), priority (LOW/MEDIUM/HIGH)",
    }

    if role in ("MANAGER", "ADMIN"):
        actions["approve_leave"] = "Approve specific leave request(s) - params: leave_ids (array of integer IDs)"
        actions["reject_leave"] = "Reject specific leave request(s) - params: leave_ids (array of integer IDs)"
        actions["approve_all_leaves"] = "Approve ALL pending leave requests - no params needed"
        actions["update_ticket_status"] = "Update a specific ticket's status - params: ticket_id (integer), new_status (OPEN/IN_PROGRESS/RESOLVED/CLOSED)"
        actions["close_all_tickets"] = "Close ALL specified open tickets - params: ticket_ids (array of integer IDs). If the user says 'close all tickets' and previous results show ticket IDs, use those IDs."

    return "\n".join(f"- {name}: {desc}" for name, desc in actions.items())


async def _execute_single_action(action: str, params: dict, confirmation: str, message: str, role: str, access_token: str) -> dict:
    # Execute action via backend API
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
        leave_ids = params.get("leave_ids") or params.get("leave_id")
        if not leave_ids:
            return {
                "answer": "I need the leave request ID(s) to approve. Please specify which leave request(s) to approve.",
                "action": action,
                "result": None
            }
            
        if not isinstance(leave_ids, list):
            if isinstance(leave_ids, str):
                import re
                nums = re.findall(r'\d+', leave_ids)
                if nums:
                    leave_ids = [int(n) for n in nums]
                else:
                    leave_ids = [leave_ids]
            else:
                leave_ids = [leave_ids]
                
        results = []
        success_count = 0
        for lid in leave_ids:
            res = await update_leave_status(int(lid), "APPROVED", access_token)
            results.append(res)
            if res.get("success"):
                success_count += 1
                
        if success_count == len(leave_ids):
            ids_str = ", ".join(f"#{lid}" for lid in leave_ids)
            return {
                "answer": f"✅ Leave request(s) {ids_str} have been approved.",
                "action": action,
                "result": {"success": True, "data": results}
            }
        elif success_count > 0:
            return {
                "answer": f"⚠️ Approved {success_count} out of {len(leave_ids)} leave requests.",
                "action": action,
                "result": {"success": True, "partial": True, "data": results}
            }
        else:
            return {
                "answer": f"❌ Failed to approve leave request(s).",
                "action": action,
                "result": {"success": False, "data": results}
            }

    elif action == "approve_all_leaves":
        from app.services.ai.api_tools import approve_all_pending_leaves
        result = await approve_all_pending_leaves(access_token)
        if result["success"]:
            count = result["data"].get("count", 0)
            if count == 0:
                return {
                    "answer": "There are no pending leave requests to approve.",
                    "action": action,
                    "result": result
                }
            return {
                "answer": f"✅ Successfully approved {count} pending leave request(s).",
                "action": action,
                "result": result
            }
        else:
            return {
                "answer": f"❌ Failed to approve all leave requests: {result.get('error', 'Unknown error')}",
                "action": action,
                "result": result
            }

    elif action == "reject_leave":
        leave_ids = params.get("leave_ids") or params.get("leave_id")
        if not leave_ids:
            return {
                "answer": "I need the leave request ID(s) to reject. Please specify which leave request(s) to reject.",
                "action": action,
                "result": None
            }
            
        if not isinstance(leave_ids, list):
            if isinstance(leave_ids, str):
                import re
                nums = re.findall(r'\d+', leave_ids)
                if nums:
                    leave_ids = [int(n) for n in nums]
                else:
                    leave_ids = [leave_ids]
            else:
                leave_ids = [leave_ids]
                
        results = []
        success_count = 0
        for lid in leave_ids:
            res = await update_leave_status(int(lid), "REJECTED", access_token)
            results.append(res)
            if res.get("success"):
                success_count += 1
                
        if success_count == len(leave_ids):
            ids_str = ", ".join(f"#{lid}" for lid in leave_ids)
            return {
                "answer": f"✅ Leave request(s) {ids_str} have been rejected.",
                "action": action,
                "result": {"success": True, "data": results}
            }
        elif success_count > 0:
            return {
                "answer": f"⚠️ Rejected {success_count} out of {len(leave_ids)} leave requests.",
                "action": action,
                "result": {"success": True, "partial": True, "data": results}
            }
        else:
            return {
                "answer": f"❌ Failed to reject leave request(s).",
                "action": action,
                "result": {"success": False, "data": results}
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

    elif action == "update_ticket_status":
        ticket_id = params.get("ticket_id")
        new_status = params.get("new_status", "").upper()
        valid_statuses = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
        if not ticket_id:
            return {
                "answer": "I need the ticket ID to update. Please specify which ticket to update (e.g., 'update ticket #5 to IN_PROGRESS').",
                "action": action,
                "result": None
            }
        if new_status not in valid_statuses:
            return {
                "answer": f"Invalid status '{new_status}'. Valid statuses are: {', '.join(valid_statuses)}.",
                "action": action,
                "result": None
            }
        res = await update_ticket_status(int(ticket_id), new_status, access_token)
        if res.get("success"):
            return {
                "answer": f"✅ Ticket #{ticket_id} has been updated to **{new_status}**.",
                "action": action,
                "result": res
            }
        else:
            return {
                "answer": f"❌ Failed to update ticket #{ticket_id}: {res.get('error', 'Unknown error')}",
                "action": action,
                "result": res
            }

    elif action == "close_all_tickets":
        ticket_ids = params.get("ticket_ids") or params.get("ticket_id")
        if not ticket_ids:
            return {
                "answer": "I need the ticket IDs to close. Please specify which tickets to close, or ask me to 'show open tickets' first so I can see the IDs.",
                "action": action,
                "result": None
            }
        if not isinstance(ticket_ids, list):
            ticket_ids = [ticket_ids]
        ticket_ids = [int(tid) for tid in ticket_ids]
        res = await close_all_open_tickets(ticket_ids, access_token)
        if res.get("success"):
            closed = res.get("success_count", 0)
            total = res.get("total", 0)
            ids_str = ", ".join(f"#{tid}" for tid in ticket_ids)
            return {
                "answer": f"✅ Successfully closed {closed}/{total} ticket(s): {ids_str}.",
                "action": action,
                "result": res
            }
        else:
            return {
                "answer": f"❌ Failed to close tickets. Please try again.",
                "action": action,
                "result": res
            }

    else:
        return {
            "answer": confirmation or "I'm not sure how to help with that.",
            "action": None,
            "result": None
        }


async def execute_hr_action(message: str, user_id: int, employee_id: int, role: str, access_token: str, history: list = None) -> dict:
    """
    Parse user intent, check permissions, and execute the HR action via backend API.
    
    Returns:
        dict with 'answer', 'action', and 'result' keys.
    """
    available_actions = _get_available_actions(role)
    llm = get_groq_llm(temperature=0.0)
    history_context = _build_history_context(history or [])

    # Step 1: Extract action intent
    from datetime import datetime
    chain = ACTION_PROMPT | llm | StrOutputParser()
    raw_response = await chain.ainvoke({
        "role": role,
        "available_actions": available_actions,
        "history_context": history_context,
        "user_id": user_id,
        "employee_id": employee_id,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
    })

    # Parse JSON from response
    try:
        cleaned = raw_response.strip()
        # Look for a markdown JSON block first
        match = re.search(r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            # Look for the outermost array or curly braces
            match_struct = re.search(r'(\[.*\]|\{.*\})', cleaned, re.DOTALL)
            if match_struct:
                cleaned = match_struct.group(1)
        action_plans = json.loads(cleaned)
        
        if isinstance(action_plans, dict):
            action_plans = [action_plans]
            
    except (json.JSONDecodeError, ValueError):
        return {
            "answer": "I had trouble understanding your request. Could you please rephrase it? For example: 'Apply sick leave from May 6 to May 7 because I have fever.'",
            "action": None,
            "result": None
        }

    combined_answers = []
    actions_taken = []
    results = []

    for action_plan in action_plans:
        action = action_plan.get("action", "none")
        params = action_plan.get("params", {})
        confirmation = action_plan.get("confirmation_message", "")

        if action == "none":
            combined_answers.append(confirmation or "I cannot perform this action.")
            continue

        if not check_permission(role, action):
            combined_answers.append(get_refusal_message(action))
            actions_taken.append(action)
            results.append({"blocked": True, "reason": "insufficient_permissions"})
            continue

        res = await _execute_single_action(action, params, confirmation, message, role, access_token)
        if res.get("answer"):
            combined_answers.append(res["answer"])
        if res.get("action"):
            actions_taken.append(res["action"])
        if res.get("result"):
            results.append(res["result"])

    if not combined_answers:
        combined_answers.append("I processed your request, but no actions were taken.")

    return {
        "answer": "\n\n".join(combined_answers),
        "action": actions_taken[0] if len(actions_taken) == 1 else actions_taken,
        "result": results[0] if len(results) == 1 else results
    }
