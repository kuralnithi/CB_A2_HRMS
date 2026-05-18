from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, Date, DateTime, Text, Float, JSON
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from app.db.base import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

class LeaveTypeEnum(str, enum.Enum):
    SICK = "SICK"
    CASUAL = "CASUAL"
    ANNUAL = "ANNUAL"


class LeaveStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProjectStatusEnum(str, enum.Enum):
    PLANNING = "PLANNING"
    ONGOING = "ONGOING"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"


class ProjectPriorityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskLevelEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class BillingTypeEnum(str, enum.Enum):
    FIXED = "FIXED"
    TIME_AND_MATERIAL = "TIME_AND_MATERIAL"
    RETAINER = "RETAINER"
    NON_BILLABLE = "NON_BILLABLE"


class EmploymentStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    BENCH = "BENCH"
    NOTICE_PERIOD = "NOTICE_PERIOD"
    RESIGNED = "RESIGNED"
    ON_LEAVE = "ON_LEAVE"


class ProjectRoleEnum(str, enum.Enum):
    PROJECT_MANAGER = "Project Manager"
    TEAM_LEAD = "Team Lead"
    DEVELOPER = "Developer"
    QA_TESTER = "QA/Tester"
    UI_UX_DESIGNER = "UI/UX Designer"
    DEVOPS_ENGINEER = "DevOps Engineer"
    BUSINESS_ANALYST = "Business Analyst"
    INTERN = "Intern"


# ─── Models ───────────────────────────────────────────────────────────────────

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)

    # Basic Info
    name = Column(String, nullable=False)
    project_code = Column(String, unique=True, nullable=True, index=True)
    client_name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    project_type = Column(String, nullable=True)  # Internal / External / R&D

    # Status & Priority
    status = Column(Enum(ProjectStatusEnum), default=ProjectStatusEnum.PLANNING, nullable=False)
    priority = Column(Enum(ProjectPriorityEnum), default=ProjectPriorityEnum.MEDIUM, nullable=False)
    risk_level = Column(Enum(RiskLevelEnum), default=RiskLevelEnum.LOW, nullable=True)

    # Dates
    start_date = Column(Date, nullable=True)
    deadline = Column(Date, nullable=True)
    estimated_completion_date = Column(Date, nullable=True)
    actual_completion_date = Column(Date, nullable=True)

    # Financials
    budget_usd = Column(Float, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    billing_type = Column(Enum(BillingTypeEnum), default=BillingTypeEnum.FIXED, nullable=True)

    # Technical
    tech_stack = Column(String, nullable=True)  # Comma-separated
    repo_url = Column(String, nullable=True)
    environment_urls = Column(Text, nullable=True)  # JSON string

    # Meta
    notes = Column(Text, nullable=True)
    is_ongoing = Column(Boolean, default=True)   # legacy compat
    is_deleted = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members = relationship("EmployeeProject", back_populates="project", lazy="select")


class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    # Personal
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    profile_photo_url = Column(String, nullable=True)

    # Professional
    employee_code = Column(String, unique=True, nullable=True, index=True)
    designation = Column(String, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    date_of_joining = Column(Date, nullable=True)
    years_of_experience = Column(Float, nullable=True)
    work_location = Column(String, nullable=True)   # Remote / On-site / Hybrid

    # Status & Allocation
    employment_status = Column(Enum(EmploymentStatusEnum), default=EmploymentStatusEnum.ACTIVE, nullable=False)
    allocation_percentage = Column(Float, default=100.0, nullable=True)
    is_billable = Column(Boolean, default=True)
    notice_period_days = Column(Integer, nullable=True)

    # Skills & Certs
    skills = Column(String, nullable=True)  # Comma-separated
    certifications = Column(String, nullable=True)  # Comma-separated

    # Sensitive Data (AI Guardrails must block these)
    bank_account_number = Column(String, nullable=True)
    pan_number = Column(String, nullable=True)
    current_salary_usd = Column(Float, nullable=True)
    hr_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project_assignments = relationship("EmployeeProject", back_populates="employee", lazy="select")


class EmployeeProject(Base):
    __tablename__ = "employee_projects"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    role_in_project = Column(String, default="Developer")
    allocation_percentage = Column(Float, default=100.0)
    is_billable = Column(Boolean, default=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    removed_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    employee = relationship("Employee", back_populates="project_assignments")
    project = relationship("Project", back_populates="members")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    leave_type = Column(Enum(LeaveTypeEnum))
    start_date = Column(Date)
    end_date = Column(Date)
    reason = Column(Text)
    status = Column(Enum(LeaveStatusEnum), default=LeaveStatusEnum.PENDING)
    reviewed_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    employee = relationship("Employee", foreign_keys=[employee_id])


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    title = Column(String)
    description = Column(Text)
    status = Column(String, default="OPEN")
    priority = Column(String, default="MEDIUM")
    created_at = Column(DateTime, default=datetime.utcnow)


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(Text)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Milestone(Base):
    __tablename__ = "milestones"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
