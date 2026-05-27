"""
Role-Based Permissions for AI features.
Determines what each role (EMPLOYEE, MANAGER, ADMIN) can do through the AI assistant.
"""

# Define which AI actions each role can perform
ROLE_PERMISSIONS = {
    "EMPLOYEE": {
        "policy_qa": True,
        "sql_query": True,  # Limited to own data
        "create_leave": True,
        "check_leave_balance": True,
        "create_ticket": True,
        "check_ticket_status": True,
        "view_own_projects": True,
        "approve_leave": False,
        "reject_leave": False,
        "approve_all_leaves": False,
        "assign_ticket": False,
        "update_ticket": False,
        "create_announcement": False,
        "assign_employee_to_project": False,
        "view_all_employees": False,
        "view_payroll": False,
    },
    "MANAGER": {
        "policy_qa": True,
        "sql_query": True,  # Team-level data
        "create_leave": True,
        "check_leave_balance": True,
        "create_ticket": True,
        "check_ticket_status": True,
        "view_own_projects": True,
        "approve_leave": True,
        "reject_leave": True,
        "approve_all_leaves": True,
        "assign_ticket": True,
        "update_ticket": True,
        "create_announcement": True,
        "assign_employee_to_project": True,
        "view_all_employees": True,  # Limited
        "view_payroll": False,
    },
    "ADMIN": {
        "policy_qa": True,
        "sql_query": True,  # Broad access
        "create_leave": True,
        "check_leave_balance": True,
        "create_ticket": True,
        "check_ticket_status": True,
        "view_own_projects": True,
        "approve_leave": True,
        "reject_leave": True,
        "approve_all_leaves": True,
        "assign_ticket": True,
        "update_ticket": True,
        "create_announcement": True,
        "assign_employee_to_project": True,
        "view_all_employees": True,
        "view_payroll": True,  # Admin only
    },
}


def check_permission(role: str, action: str) -> bool:
    """Check if a role has permission to perform an action."""
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["EMPLOYEE"])
    return perms.get(action, False)


def get_refusal_message(action: str) -> str:
    """Return a safe refusal message that doesn't leak information."""
    refusals = {
        "approve_leave": "You do not have permission to approve leave requests.",
        "reject_leave": "You do not have permission to reject leave requests.",
        "assign_ticket": "You do not have permission to assign tickets.",
        "update_ticket": "You do not have permission to update tickets.",
        "create_announcement": "You do not have permission to create announcements.",
        "assign_employee_to_project": "You do not have permission to assign employees to projects.",
        "view_all_employees": "You do not have permission to view all employee data.",
        "view_payroll": "You do not have permission to access payroll information.",
        "view_company_data": "🔒 **Access Restricted** — As an employee, you can only access your own data. Company-wide information such as all projects, all employees, or department-level data is not available to you. Please ask about your own records (e.g., \"my projects\", \"my leave balance\", \"my tickets\").",
    }
    return refusals.get(action, "You do not have permission to perform this action.")
