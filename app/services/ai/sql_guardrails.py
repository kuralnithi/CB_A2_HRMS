"""
SQL Guardrails for the SQL Agent.
Validates generated SQL to ensure safety:
- Only SELECT statements allowed
- No DDL/DML operations
- Sensitive columns are blocked
- Single-statement only
- Row limit enforced
"""
import re
from typing import Optional

# Forbidden SQL keywords (DDL/DML)
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "REPLACE", "TRUNCATE", "PRAGMA", "ATTACH", "DETACH",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "MERGE", "CALL",
]

# Sensitive columns that must never appear in queries
FORBIDDEN_COLUMNS = [
    "hashed_password",
    "bank_account_number",
    "bank_account_name",
    "bank_branch",
    "bank_ifsc",
    "pan_number",
    "pan_name",
    "pan_dob",
    "date_of_birth",
    "current_salary_usd",
    "profile_photo_path",
    "profile_photo_mime",
]

MAX_ROWS = 50


def validate_sql(sql: str) -> tuple[bool, Optional[str]]:
    """
    Validate a generated SQL query for safety.

    Returns:
        (is_safe, error_message) - (True, None) if safe, (False, reason) if unsafe.
    """
    if not sql or not sql.strip():
        return False, "Empty SQL query."

    sql_upper = sql.upper().strip()

    # 1. Must be a SELECT statement
    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed. Mutation operations are blocked."

    # 2. Check for forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        # Use word boundary to avoid false positives (e.g., "CREATED_AT")
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"Forbidden SQL operation detected: {keyword}. Only read-only queries are allowed."

    # 3. Check for multiple statements (semicolons)
    # Remove strings first to avoid false positives
    sql_no_strings = re.sub(r"'[^']*'", "", sql)
    if sql_no_strings.count(";") > 1:
        return False, "Multiple SQL statements are not allowed. Please submit one query at a time."

    # 4. Check for forbidden columns
    sql_lower = sql.lower()
    for col in FORBIDDEN_COLUMNS:
        if col in sql_lower:
            return False, f"Access to sensitive column '{col}' is blocked for security reasons."

    # 5. Check for subqueries that might contain mutations
    if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|ALTER)\b', sql_upper.replace("SELECT", "", 1)):
        return False, "Suspicious SQL pattern detected. Query blocked."

    return True, None


def add_row_limit(sql: str, limit: int = MAX_ROWS) -> str:
    """Add a LIMIT clause if not already present."""
    sql_upper = sql.upper().strip().rstrip(";")
    if "LIMIT" not in sql_upper:
        return f"{sql.strip().rstrip(';')} LIMIT {limit};"
    return sql


def get_safe_schema_for_role(role: str) -> str:
    """
    Returns the database schema description filtered by role.
    Sensitive columns are excluded from all roles.
    """
    base_schema = """
Available tables and columns:

TABLE: employees
  - id (INTEGER, primary key)
  - user_id (INTEGER, foreign key to users.id)
  - name (VARCHAR, employee full name)
  - department_id (INTEGER, foreign key to departments.id)
  - manager_id (INTEGER, foreign key to employees.id, nullable)
  - skills (VARCHAR, comma-separated skill list)

TABLE: departments
  - id (INTEGER, primary key)
  - name (VARCHAR, unique department name)

TABLE: projects
  - id (INTEGER, primary key)
  - name (VARCHAR, project name)
  - description (TEXT)
  - is_ongoing (BOOLEAN, true if project is active)

TABLE: employee_projects
  - id (INTEGER, primary key)
  - employee_id (INTEGER, foreign key to employees.id)
  - project_id (INTEGER, foreign key to projects.id)
  - role_in_project (VARCHAR)

TABLE: leave_requests
  - id (INTEGER, primary key)
  - employee_id (INTEGER, foreign key to employees.id)
  - leave_type (ENUM: SICK, CASUAL, ANNUAL)
  - start_date (DATE)
  - end_date (DATE)
  - reason (TEXT)
  - status (ENUM: PENDING, APPROVED, REJECTED)

TABLE: tickets
  - id (INTEGER, primary key)
  - employee_id (INTEGER, foreign key to employees.id)
  - title (VARCHAR)
  - description (TEXT)
  - status (VARCHAR, default OPEN)

TABLE: announcements
  - id (INTEGER, primary key)
  - title (VARCHAR)
  - content (TEXT)
  - created_at (DATETIME)

TABLE: users
  - id (INTEGER, primary key)
  - email (VARCHAR)
  - role (ENUM: EMPLOYEE, MANAGER, ADMIN)
  - is_active (BOOLEAN)

NOTE: Never include hashed_password, bank_account_number, pan_number, current_salary_usd, or any other sensitive columns in queries.
"""

    role_notes = {
        "EMPLOYEE": "\nROLE RESTRICTION: You are querying as an EMPLOYEE. Only return data that belongs to the current user (filter by employee_id or user_id). Do not return other employees' personal information.",
        "MANAGER": "\nROLE RESTRICTION: You are querying as a MANAGER. You can view data for employees in your team/department. Do not expose salary or banking information.",
        "ADMIN": "\nROLE RESTRICTION: You are querying as an ADMIN. You have broad access but must NEVER include sensitive columns (salary, bank, PAN, password).",
    }

    return base_schema + role_notes.get(role, role_notes["EMPLOYEE"])
