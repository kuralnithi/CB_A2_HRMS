"""
AI Audit Logging service.
Logs every AI interaction to the ai_audit_logs table.

What to log: user_id, role, message, intent, tool_name, action_status, records_accessed, timestamp.
What NOT to log: secrets, full JWTs, passwords, bank/PAN details.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai import AIAuditLog


async def log_ai_interaction(
    db: AsyncSession,
    user_id: int,
    role: str,
    message: str,
    intent: str = None,
    tool_name: str = None,
    action_status: str = None,
    records_accessed: str = None,
):
    """
    Log an AI interaction to the audit table.
    """
    audit_entry = AIAuditLog(
        user_id=user_id,
        role=role,
        message=message[:2000],  # Truncate to avoid excessively long messages
        intent=intent,
        tool_name=tool_name,
        action_status=action_status,
        records_accessed=records_accessed,
    )
    db.add(audit_entry)
    await db.commit()
    return audit_entry
