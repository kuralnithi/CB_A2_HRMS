from fastapi import APIRouter
from app.api.v1.endpoints import auth, leaves, projects, chat, dashboard, employees, tickets, admin

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(leaves.router, prefix="/leaves", tags=["leaves"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
