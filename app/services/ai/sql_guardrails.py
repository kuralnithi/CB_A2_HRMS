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


def validate_sql(sql: str, role: str = "EMPLOYEE") -> tuple[bool, Optional[str]]:
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

    # 4. Check for forbidden columns (except authorized ones for ADMIN role)
    sql_lower = sql.lower()
    role_forbidden = FORBIDDEN_COLUMNS.copy()
    if "current_salary_usd" in role_forbidden:
        role_forbidden.remove("current_salary_usd")
    if "date_of_birth" in role_forbidden:
        role_forbidden.remove("date_of_birth")
        
    if role == "EMPLOYEE":
        role_forbidden.extend(["budget_usd", "estimated_cost", "actual_cost", "billing_type"])

    for col in role_forbidden:
        if col in sql_lower:
            return False, f"Access to sensitive column '{col}' is blocked for security reasons."

    # 5. Check for subqueries that might contain mutations
    if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|ALTER)\b', sql_upper.replace("SELECT", "", 1)):
        return False, "Suspicious SQL pattern detected. Query blocked."

    return True, None


def add_row_limit(sql: str, limit: int = MAX_ROWS) -> str:
    """
    Add a LIMIT clause if not already present, unless it's a scalar aggregate query.
    Also strips LIMIT from scalar aggregates if already present to avoid confusing the LLM.
    """
    sql_upper = sql.upper().strip().rstrip(";")
    
    # Check if it's a scalar aggregate query (contains aggregate function and no GROUP BY)
    has_aggregate = bool(re.search(r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(', sql_upper))
    has_group_by = "GROUP BY" in sql_upper
    
    if has_aggregate and not has_group_by:
        cleaned_sql = re.sub(r'(?i)\bLIMIT\s+\d+\b', '', sql)
        return re.sub(r'\s*;+\s*$', '', cleaned_sql).strip() + ";"
        
    if "LIMIT" not in sql_upper:
        return f"{sql.strip().rstrip(';')} LIMIT {limit};"
    return sql


def get_safe_schema_for_role(role: str) -> str:
    """
    Returns the database schema description filtered by role.
    Sensitive columns are excluded from all roles unless authorized.
    """
    salary_col = "  - current_salary_usd (DOUBLE PRECISION, employee monthly salary in USD)\n"
    dob_col = "  - date_of_birth (DATE, employee date of birth)\n"
    phone_col = "  - phone (VARCHAR, employee phone number)\n"
    gender_col = "  - gender (VARCHAR, employee gender)\n"
    
    budget_col = "  - budget_usd (DOUBLE PRECISION)\n" if role != "EMPLOYEE" else ""
    est_cost_col = "  - estimated_cost (DOUBLE PRECISION)\n" if role != "EMPLOYEE" else ""
    act_cost_col = "  - actual_cost (DOUBLE PRECISION)\n" if role != "EMPLOYEE" else ""
    billing_col = "  - billing_type (VARCHAR)\n" if role != "EMPLOYEE" else ""

    base_schema = f"""
Available tables and columns:

TABLE: employees
  - id (INTEGER, primary key)
  - user_id (INTEGER, foreign key to users.id)
  - name (VARCHAR, employee full name)
  - department_id (INTEGER, foreign key to departments.id)
  - manager_id (INTEGER, foreign key to employees.id, nullable)
  - skills (VARCHAR, comma-separated skill list)
{salary_col}{dob_col}{phone_col}{gender_col}  - employee_code (VARCHAR, unique employee code)
  - designation (VARCHAR, job title)
  - date_of_joining (DATE)
  - years_of_experience (DOUBLE PRECISION)
  - work_location (VARCHAR)
  - employment_status (VARCHAR(13), e.g. ACTIVE, BENCH, NOTICE_PERIOD, RESIGNED, ON_LEAVE)
  - allocation_percentage (DOUBLE PRECISION)
  - is_billable (BOOLEAN)
  - notice_period_days (INTEGER)
  - certifications (VARCHAR)

TABLE: departments
  - id (INTEGER, primary key)
  - name (VARCHAR, unique department name)

TABLE: projects
  - id (INTEGER, primary key)
  - name (VARCHAR, project name)
  - description (TEXT)
  - is_ongoing (BOOLEAN, true if project is active)
  - project_code (VARCHAR)
  - client_name (VARCHAR)
  - project_type (VARCHAR)
  - status (VARCHAR, e.g. PLANNING, ONGOING, ON_HOLD, COMPLETED, DELAYED, CANCELLED)
  - priority (VARCHAR)
{budget_col}{est_cost_col}{act_cost_col}{billing_col}  - tech_stack (VARCHAR)

TABLE: employee_projects
  - id (INTEGER, primary key)
  - employee_id (INTEGER, foreign key to employees.id)
  - project_id (INTEGER, foreign key to projects.id)
  - role_in_project (VARCHAR, e.g. 'Project Manager', 'Developer', 'UI/UX Designer')
  - allocation_percentage (DOUBLE PRECISION)
  - is_active (BOOLEAN)

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
  - priority (VARCHAR)

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

NOTE: Never include hashed_password, bank_account_number, pan_number, or other sensitive columns in queries.
"""

    role_notes = {
        "EMPLOYEE": "\nROLE RESTRICTION: You are querying as an EMPLOYEE. Only return data that belongs to the current user (filter by employee_id or user_id). You are allowed to return the current_salary_usd for the current user. Do not return other employees' personal information.",
        "MANAGER": "\nROLE RESTRICTION: You are querying as a MANAGER. You can view data for employees in your team/department. Do not expose salary or banking information of other employees (you may only access your own salary if explicitly requested).",
        "ADMIN": "\nROLE RESTRICTION: You are querying as an ADMIN. You have broad access to all database tables. You are explicitly authorized to use current_salary_usd for calculating payroll summaries, salary distributions, department budget analytics, and individual salary lookups.",
    }

    return base_schema + role_notes.get(role, role_notes["EMPLOYEE"])
