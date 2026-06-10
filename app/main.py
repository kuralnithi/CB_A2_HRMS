import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.init_db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB and seed data
    try:
        await init_db()
    except Exception as e:
        print(f"Error during database initialization: {e}")
    yield
    # Shutdown (if any)

app = FastAPI(
    title="NovaWorks PeopleOps Copilot API",
    version="1.0.0",
    description="Full-stack AI HRMS Backend",
    lifespan=lifespan
)

# Ensure upload directory exists
UPLOAD_DIR = "static/uploads/profile_photos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to NovaWorks PeopleOps API"}
