"""
SQL Agent for HR Intelligence.
Generates safe, read-only SQL from natural language and executes against PostgreSQL.

Safety:
- Only SELECT queries allowed
- Sensitive columns blocked
- Role-based data filtering
- Row limits enforced
- Safe error handling (no raw DB errors to user)
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.llm import get_groq_llm
from app.services.ai.sql_guardrails import (
    validate_sql, add_row_limit, get_safe_schema_for_role
)
from app.core.config import settings

import sqlalchemy
import re

SQL_AGENT_SYSTEM_PROMPT = """You are a read-only SQL assistant for the NovaWorks HRMS database (PostgreSQL).

Your job is to convert the user's natural language question into a SAFE, READ-ONLY SQL query.

DATABASE SCHEMA:
{schema}

STRICT RULES:
1. Generate ONLY SELECT statements. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, or any mutation.
2. Never include sensitive columns: {sensitive_cols}, bank_branch, bank_ifsc, pan_name, pan_dob, profile_photo_path, profile_photo_mime.
3. Always add a LIMIT clause (max 50 rows), except for scalar aggregate queries (like COUNT(*), SUM(), AVG() without a GROUP BY) which naturally return exactly one row.
4. Use proper JOINs when querying across tables.
5. Return ONLY the SQL query, nothing else. No explanations, no markdown formatting.
6. If the question cannot be answered with a SQL query, return exactly: CANNOT_GENERATE_SQL
7. {role_filter}
8. LEAVE BALANCE RULES: Each employee gets 20 total leaves per year.
   - "remaining leaves" or "balance leaves" = 20 - COALESCE(SUM(end_date - start_date + 1), 0) of APPROVED leave requests for that employee.
   - "used leaves" or "approved leaves" (in days) = COALESCE(SUM(end_date - start_date + 1), 0) of APPROVED leave requests.
   - "pending leaves" (in days) = COALESCE(SUM(end_date - start_date + 1), 0) of PENDING leave requests.
   - For "remaining leaves" or "leave balance" queries, always compute: SELECT (20 - COALESCE(SUM(end_date - start_date + 1), 0)) AS remaining_leaves FROM leave_requests WHERE employee_id = (...) AND status = 'APPROVED'
   - You can also filter by leave_type (SICK, CASUAL, ANNUAL) if asked.
9. When joining employees table to get an employee by name, use: WHERE LOWER(e.name) LIKE LOWER('%name%')
10. PROJECT MANAGERS: To find the manager of a project, join the employee_projects table and filter by `role_in_project = 'Project Manager'`. Do NOT use `employees.manager_id` for project managers.
11. INCLUSION OF FILTER COLUMNS: If the user asks to filter by specific statuses (e.g. "ongoing and delayed"), you MUST include that column (e.g. `p.status`) in the SELECT statement so the user can see it in the output table.

CURRENT USER INFO:
- User ID: {user_id}
- Employee ID: {employee_id}
- Role: {role}
- Current Date/Time: {current_time}
"""

SQL_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SQL_AGENT_SYSTEM_PROMPT),
    ("human", "{question}")
])

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an HR data assistant. Given the user's question and the SQL query results, 
provide a clear, helpful summary. Format the answer naturally. 
If results are empty, say so politely. Never reveal sensitive data."""),
    ("human", """Question: {question}
SQL Query: {sql}
Results: {results}

Provide a concise, helpful answer based on these results.""")
])


def _get_sync_connection_string():
    """Get synchronous database connection string for SQL execution."""
    if settings.DATABASE_URL:
        url = settings.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url

    import urllib.parse
    encoded_password = urllib.parse.quote_plus(settings.POSTGRES_PASSWORD)
    return f"postgresql://{settings.POSTGRES_USER}:{encoded_password}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"


async def query_sql_agent(question: str, user_id: int, employee_id: int, role: str) -> dict:
    """
    Convert natural language to SQL, validate, execute, and summarize.
    
    Returns:
        dict with 'answer', 'sql', and 'rows' keys.
    """
    schema = get_safe_schema_for_role(role)

    # Role-specific WHERE clause hints
    role_filter = ""
    if role == "EMPLOYEE":
        role_filter = (
            f"STRICT SECURITY RULE: You are ONLY allowed to query data belonging to the current user. "
            f"If the table has an 'employee_id' column, you MUST filter by 'employee_id = {employee_id}'. "
            f"If the table has a 'user_id' column, you MUST filter by 'user_id = {user_id}'. "
            f"NEVER use the user_id value ({user_id}) for the employee_id column, and NEVER use the employee_id value ({employee_id}) for the user_id column. "
            f"If the user asks for information about other employees, departments, or company-wide data, you MUST return exactly: CANNOT_GENERATE_SQL"
        )
    elif role == "MANAGER":
        role_filter = f"You may query data for employees who report to employee_id = {employee_id} (manager_id = {employee_id}), plus your own data."
    else:
        role_filter = "You have broad access to query all employee data including salary analytics, budget metrics, and payroll. Exclude only direct banking credentials."

    # Define forbidden columns list dynamically for LLM instruction
    if role == "ADMIN":
        sensitive_cols = "hashed_password, bank_account_number, pan_number"
    elif role == "EMPLOYEE":
        sensitive_cols = "hashed_password, bank_account_number, pan_number, budget_usd, estimated_cost, actual_cost, billing_type"
    else:
        sensitive_cols = "hashed_password, bank_account_number, pan_number"

    llm = get_groq_llm(temperature=0.0)

    # Step 1: Generate SQL
    from datetime import datetime
    chain = SQL_AGENT_PROMPT | llm | StrOutputParser()
    raw_sql = await chain.ainvoke({
        "schema": schema,
        "role_filter": role_filter,
        "sensitive_cols": sensitive_cols,
        "user_id": user_id,
        "employee_id": employee_id,
        "role": role,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question": question,
    })

    # Clean the SQL output (remove markdown code fences if present)
    raw_sql = raw_sql.strip()
    raw_sql = re.sub(r'^```sql\s*', '', raw_sql)
    raw_sql = re.sub(r'\s*```$', '', raw_sql)
    raw_sql = raw_sql.strip()

    if raw_sql == "CANNOT_GENERATE_SQL":
        return {
            "answer": "I'm unable to generate a database query for this question. It may be outside the scope of HR data queries.",
            "sql": None,
            "rows": []
        }

    # Step 2: Validate SQL
    is_safe, error = validate_sql(raw_sql, role)
    if not is_safe:
        return {
            "answer": f"⚠️ {error}",
            "sql": None,
            "rows": []
        }

    # Step 3: Add row limit
    safe_sql = add_row_limit(raw_sql)

    import decimal
    import datetime
    
    def sanitize_val(val):
        if isinstance(val, decimal.Decimal):
            return float(val)
        if isinstance(val, (datetime.date, datetime.datetime)):
            return str(val)
        return val

    # Step 4: Execute SQL
    try:
        engine = sqlalchemy.create_engine(_get_sync_connection_string())
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(safe_sql))
            columns = list(result.keys())
            rows = [{k: sanitize_val(v) for k, v in zip(columns, row)} for row in result.fetchall()]
    except Exception:
        return {
            "answer": "I encountered an issue while processing your query. Please try rephrasing your question.",
            "sql": safe_sql,
            "rows": []
        }

    # Step 5: Generate natural language answer
    answer_chain = ANSWER_PROMPT | llm | StrOutputParser()
    answer = await answer_chain.ainvoke({
        "question": question,
        "sql": safe_sql,
        "results": str(rows[:10]),  # Limit context for LLM
    })

    # Hide SQL from non-admin/manager roles
    visible_sql = safe_sql if role in ("ADMIN", "MANAGER") else None

    # Step 6: Generate Deterministic Chart Metadata
    from app.services.ai.analytics import generate_rendering_metadata
    metadata = generate_rendering_metadata(rows)

    return {
        "answer": answer,
        "sql": visible_sql,
        "rows": rows,
        "dev_metadata": metadata
    }
