from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.db.base import Base

class AIAuditLog(Base):
    __tablename__ = "ai_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    intent = Column(String(50))
    tool_name = Column(String(100))
    action_status = Column(String(30))
    records_accessed = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
