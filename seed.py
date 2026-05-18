import asyncio
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.models.hr import (
    Employee, Department, Project, EmployeeProject, LeaveRequest,
    Ticket, Announcement, Milestone,
    LeaveTypeEnum, LeaveStatusEnum, ProjectStatusEnum, ProjectPriorityEnum,
    RiskLevelEnum, BillingTypeEnum, EmploymentStatusEnum
)
from app.core.security import get_password_hash

async def seed_data():
    async with AsyncSessionLocal() as db:
        # ── Users ────────────────────────────────────────────────────────────
        admin_user = User(email="admin@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.ADMIN)
        manager_user = User(email="manager@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.MANAGER)
        manager2_user = User(email="manager2@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.MANAGER)
        emp1_user = User(email="employee@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.EMPLOYEE)
        emp2_user = User(email="priya@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.EMPLOYEE)
        emp3_user = User(email="arjun@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.EMPLOYEE)
        emp4_user = User(email="deepa@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.EMPLOYEE)
        emp5_user = User(email="vikram@novaworks.local", hashed_password=get_password_hash("password123"), role=RoleEnum.EMPLOYEE)

        db.add_all([admin_user, manager_user, manager2_user, emp1_user, emp2_user, emp3_user, emp4_user, emp5_user])
        await db.commit()
        for u in [admin_user, manager_user, manager2_user, emp1_user, emp2_user, emp3_user, emp4_user, emp5_user]:
            await db.refresh(u)

        # ── Departments ───────────────────────────────────────────────────────
        hr_dept = Department(name="Human Resources")
        eng_dept = Department(name="Engineering")
        design_dept = Department(name="Design")
        qa_dept = Department(name="QA & Testing")
        devops_dept = Department(name="DevOps")
        db.add_all([hr_dept, eng_dept, design_dept, qa_dept, devops_dept])
        await db.commit()
        for d in [hr_dept, eng_dept, design_dept, qa_dept, devops_dept]:
            await db.refresh(d)

        # ── Employees ─────────────────────────────────────────────────────────
        today = date.today()
        admin_emp = Employee(
            user_id=admin_user.id, name="Admin User", employee_code="EMP001",
            designation="HR Director", department_id=hr_dept.id,
            skills="HR Management, Policy", employment_status=EmploymentStatusEnum.ACTIVE,
            date_of_joining=date(2019, 1, 15), work_location="On-site",
            years_of_experience=8.0, gender="Male", phone="+91-9000000001",
            is_billable=False, allocation_percentage=0.0, current_salary_usd=150000
        )
        manager_emp = Employee(
            user_id=manager_user.id, name="Karthik Raj", employee_code="EMP002",
            designation="Engineering Manager", department_id=eng_dept.id,
            skills="Python, Leadership, System Design, FastAPI",
            employment_status=EmploymentStatusEnum.ACTIVE,
            date_of_joining=date(2020, 3, 10), work_location="Hybrid",
            years_of_experience=7.0, gender="Male", phone="+91-9000000002",
            is_billable=True, allocation_percentage=80.0, current_salary_usd=120000
        )
        manager2_emp = Employee(
            user_id=manager2_user.id, name="Sneha Patel", employee_code="EMP003",
            designation="QA Manager", department_id=qa_dept.id,
            skills="Testing, Selenium, Leadership, Automation",
            employment_status=EmploymentStatusEnum.ACTIVE,
            date_of_joining=date(2021, 6, 1), work_location="Remote",
            years_of_experience=5.0, gender="Female", phone="+91-9000000003",
            is_billable=True, allocation_percentage=100.0, current_salary_usd=100000
        )

        db.add_all([admin_emp, manager_emp, manager2_emp])
        await db.commit()
        for e in [admin_emp, manager_emp, manager2_emp]:
            await db.refresh(e)

        emp1 = Employee(
            user_id=emp1_user.id, name="Rahul Kumar", employee_code="EMP004",
            designation="Senior Backend Engineer", department_id=eng_dept.id,
            manager_id=manager_emp.id, skills="Python, FastAPI, PostgreSQL, LangChain",
            certifications="AWS Solutions Architect",
            employment_status=EmploymentStatusEnum.ACTIVE,
            date_of_joining=date(2022, 1, 20), work_location="Hybrid",
            years_of_experience=4.0, gender="Male", phone="+91-9000000004",
            is_billable=True, allocation_percentage=100.0, current_salary_usd=80000
        )
        emp2 = Employee(
            user_id=emp2_user.id, name="Priya Sharma", employee_code="EMP005",
            designation="Frontend Engineer", department_id=eng_dept.id,
            manager_id=manager_emp.id, skills="React, Next.js, TypeScript, TailwindCSS",
            certifications="Google Cloud Professional",
            employment_status=EmploymentStatusEnum.ACTIVE,
            date_of_joining=date(2022, 5, 15), work_location="Remote",
            years_of_experience=3.0, gender="Female", phone="+91-9000000005",
            is_billable=True, allocation_percentage=100.0, current_salary_usd=75000
        )
        emp3 = Employee(
            user_id=emp3_user.id, name="Arjun Singh", employee_code="EMP006",
            designation="DevOps Engineer", department_id=devops_dept.id,
            manager_id=manager_emp.id, skills="Docker, Kubernetes, Terraform, AWS, GCP",
            certifications="CKA, AWS DevOps",
            employment_status=EmploymentStatusEnum.BENCH,
            date_of_joining=date(2021, 9, 1), work_location="Remote",
            years_of_experience=5.0, gender="Male", phone="+91-9000000006",
            is_billable=False, allocation_percentage=0.0, current_salary_usd=90000
        )
        emp4 = Employee(
            user_id=emp4_user.id, name="Deepa Menon", employee_code="EMP007",
            designation="UI/UX Designer", department_id=design_dept.id,
            manager_id=manager_emp.id, skills="Figma, Adobe XD, Prototyping, User Research",
            employment_status=EmploymentStatusEnum.ACTIVE,
            date_of_joining=date(2023, 2, 10), work_location="On-site",
            years_of_experience=2.0, gender="Female", phone="+91-9000000007",
            is_billable=True, allocation_percentage=100.0, current_salary_usd=65000
        )
        emp5 = Employee(
            user_id=emp5_user.id, name="Vikram Nair", employee_code="EMP008",
            designation="QA Engineer", department_id=qa_dept.id,
            manager_id=manager2_emp.id, skills="Selenium, Pytest, API Testing, Postman",
            employment_status=EmploymentStatusEnum.NOTICE_PERIOD,
            date_of_joining=date(2020, 11, 5), work_location="Hybrid",
            notice_period_days=60, years_of_experience=6.0, gender="Male",
            phone="+91-9000000008", is_billable=True, allocation_percentage=100.0,
            current_salary_usd=85000
        )

        db.add_all([emp1, emp2, emp3, emp4, emp5])
        await db.commit()
        for e in [emp1, emp2, emp3, emp4, emp5]:
            await db.refresh(e)

        # ── Projects ──────────────────────────────────────────────────────────
        proj1 = Project(
            name="HR Policy Copilot", project_code="NW-001",
            client_name="Internal", description="AI Copilot for HR policy Q&A and task automation",
            project_type="Internal", status=ProjectStatusEnum.ONGOING,
            priority=ProjectPriorityEnum.HIGH, risk_level=RiskLevelEnum.MEDIUM,
            start_date=date(2025, 1, 1), deadline=date(2025, 12, 31),
            budget_usd=250000, estimated_cost=200000, actual_cost=120000,
            billing_type=BillingTypeEnum.NON_BILLABLE,
            tech_stack="Python, FastAPI, LangChain, PostgreSQL, Next.js",
            repo_url="https://github.com/novaworks/hr-copilot",
            notes="Capstone project for AI integration",
            is_ongoing=True, is_deleted=False, is_archived=False
        )
        proj2 = Project(
            name="E-Commerce Platform", project_code="NW-002",
            client_name="RetailCo Ltd", description="End-to-end e-commerce solution with AI recommendations",
            project_type="External", status=ProjectStatusEnum.ONGOING,
            priority=ProjectPriorityEnum.CRITICAL, risk_level=RiskLevelEnum.HIGH,
            start_date=date(2025, 3, 1), deadline=today + timedelta(days=90),
            budget_usd=500000, estimated_cost=450000, actual_cost=200000,
            billing_type=BillingTypeEnum.TIME_AND_MATERIAL,
            tech_stack="React, Node.js, PostgreSQL, Redis, AWS",
            repo_url="https://github.com/novaworks/ecommerce",
            is_ongoing=True, is_deleted=False, is_archived=False
        )
        proj3 = Project(
            name="Data Analytics Dashboard", project_code="NW-003",
            client_name="FinTech Solutions", description="Real-time business intelligence dashboard",
            project_type="External", status=ProjectStatusEnum.COMPLETED,
            priority=ProjectPriorityEnum.MEDIUM, risk_level=RiskLevelEnum.LOW,
            start_date=date(2024, 6, 1), deadline=date(2024, 12, 31),
            actual_completion_date=date(2024, 12, 20),
            budget_usd=180000, estimated_cost=160000, actual_cost=155000,
            billing_type=BillingTypeEnum.FIXED,
            tech_stack="Python, Pandas, Tableau, PostgreSQL",
            is_ongoing=False, is_deleted=False, is_archived=False
        )
        proj4 = Project(
            name="Mobile Banking App", project_code="NW-004",
            client_name="BankXYZ", description="Cross-platform mobile banking application",
            project_type="External", status=ProjectStatusEnum.ON_HOLD,
            priority=ProjectPriorityEnum.HIGH, risk_level=RiskLevelEnum.HIGH,
            start_date=date(2025, 2, 1), deadline=today + timedelta(days=180),
            budget_usd=750000, estimated_cost=700000,
            billing_type=BillingTypeEnum.FIXED,
            tech_stack="React Native, Node.js, MongoDB",
            notes="On hold due to client regulatory approval",
            is_ongoing=False, is_deleted=False, is_archived=False
        )

        db.add_all([proj1, proj2, proj3, proj4])
        await db.commit()
        for p in [proj1, proj2, proj3, proj4]:
            await db.refresh(p)

        # ── Team Assignments ─────────────────────────────────────────────────
        assignments = [
            EmployeeProject(employee_id=emp1.id, project_id=proj1.id, role_in_project="Developer", allocation_percentage=60.0, is_billable=False, is_active=True),
            EmployeeProject(employee_id=emp1.id, project_id=proj2.id, role_in_project="Developer", allocation_percentage=40.0, is_billable=True, is_active=True),
            EmployeeProject(employee_id=emp2.id, project_id=proj1.id, role_in_project="Developer", allocation_percentage=50.0, is_billable=False, is_active=True),
            EmployeeProject(employee_id=emp2.id, project_id=proj2.id, role_in_project="Developer", allocation_percentage=50.0, is_billable=True, is_active=True),
            EmployeeProject(employee_id=emp4.id, project_id=proj2.id, role_in_project="UI/UX Designer", allocation_percentage=100.0, is_billable=True, is_active=True),
            EmployeeProject(employee_id=manager_emp.id, project_id=proj1.id, role_in_project="Project Manager", allocation_percentage=20.0, is_billable=False, is_active=True),
            EmployeeProject(employee_id=manager_emp.id, project_id=proj2.id, role_in_project="Project Manager", allocation_percentage=30.0, is_billable=True, is_active=True),
            EmployeeProject(employee_id=emp5.id, project_id=proj3.id, role_in_project="QA/Tester", allocation_percentage=100.0, is_billable=True, is_active=True),
        ]
        db.add_all(assignments)
        await db.commit()

        # ── Leave Requests ────────────────────────────────────────────────────
        leaves = [
            LeaveRequest(employee_id=emp1.id, leave_type=LeaveTypeEnum.CASUAL, start_date=today + timedelta(days=3), end_date=today + timedelta(days=4), reason="Personal work", status=LeaveStatusEnum.PENDING),
            LeaveRequest(employee_id=emp2.id, leave_type=LeaveTypeEnum.SICK, start_date=today - timedelta(days=5), end_date=today - timedelta(days=4), reason="Fever", status=LeaveStatusEnum.APPROVED),
            LeaveRequest(employee_id=emp3.id, leave_type=LeaveTypeEnum.ANNUAL, start_date=today + timedelta(days=10), end_date=today + timedelta(days=14), reason="Vacation", status=LeaveStatusEnum.PENDING),
            LeaveRequest(employee_id=emp5.id, leave_type=LeaveTypeEnum.CASUAL, start_date=today - timedelta(days=2), end_date=today - timedelta(days=1), reason="Family function", status=LeaveStatusEnum.APPROVED),
        ]
        db.add_all(leaves)

        # ── Tickets ───────────────────────────────────────────────────────────
        tickets = [
            Ticket(employee_id=emp1.id, title="VPN not connecting", description="Unable to connect to office VPN", status="OPEN", priority="HIGH"),
            Ticket(employee_id=emp2.id, title="Laptop overheating", description="Laptop shuts down after 1 hour of use", status="OPEN", priority="MEDIUM"),
            Ticket(employee_id=emp3.id, title="Access to AWS console", description="Need access to production AWS console", status="CLOSED", priority="HIGH"),
            Ticket(employee_id=emp4.id, title="Figma license renewal", description="Current Figma license expires this month", status="OPEN", priority="LOW"),
        ]
        db.add_all(tickets)

        # ── Announcements ─────────────────────────────────────────────────────
        announcements = [
            Announcement(title="Q2 Town Hall Meeting", content="Friday's town hall has been moved to 5 PM. All employees are requested to attend.", created_by=admin_emp.id),
            Announcement(title="New Leave Policy", content="Starting next quarter, annual leave quota increases to 24 days. Check the HR portal for details.", created_by=admin_emp.id),
            Announcement(title="Office Relocation", content="Our Bangalore office moves to the new premises on June 1st. Transport arrangements will be provided.", created_by=admin_emp.id),
        ]
        db.add_all(announcements)

        # ── Milestones ────────────────────────────────────────────────────────
        milestones = [
            Milestone(project_id=proj1.id, title="Phase 1: Policy RAG", description="Complete RAG pipeline for HR policies", due_date=date(2025, 6, 30), is_completed=True),
            Milestone(project_id=proj1.id, title="Phase 2: SQL Agent", description="Natural language SQL queries", due_date=date(2025, 9, 30), is_completed=False),
            Milestone(project_id=proj2.id, title="MVP Launch", description="Launch MVP with core e-commerce features", due_date=today + timedelta(days=45), is_completed=False),
            Milestone(project_id=proj2.id, title="AI Recommendations", description="Integrate AI product recommendations", due_date=today + timedelta(days=90), is_completed=False),
        ]
        db.add_all(milestones)

        await db.commit()
        print("SUCCESS: Database seeded successfully with rich enterprise data!")


if __name__ == "__main__":
    asyncio.run(seed_data())
