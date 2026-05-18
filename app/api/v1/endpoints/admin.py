import logging
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, RoleEnum
from app.services.ai.ingestion.chunker import create_chunks
from app.services.ai.vector_store import add_chunks

import uuid
from typing import Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple in-memory job tracker for progress tracking
JOB_STATUS: Dict[str, Dict[str, Any]] = {}

def require_admin(user: User = Depends(get_current_user)) -> User:
    """Only ADMIN users can access admin endpoints."""
    if user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def process_and_ingest(job_id: str, file_path: str, filename: str, collection: str):
    """Background task to parse and ingest the document."""
    try:
        JOB_STATUS[job_id] = {"status": "processing", "progress": 10, "message": "Parsing document structure..."}
        logger.info(f"Starting ingestion for {filename} (Job: {job_id})")
        
        # Pass a callback to chunker to update progress if we want, or just rely on stages
        chunks = create_chunks(
            filepath=file_path,
            original_filename=filename,
            collection=collection,
            access_roles=["EMPLOYEE", "MANAGER", "ADMIN"],
            progress_callback=lambda p, m: JOB_STATUS[job_id].update({"progress": p, "message": m})
        )
        
        if not chunks:
            JOB_STATUS[job_id] = {"status": "error", "progress": 0, "message": "No chunks extracted"}
            logger.warning(f"No chunks created for {filename}")
            return
            
        JOB_STATUS[job_id] = {"status": "processing", "progress": 85, "message": "Indexing to Vector DB..."}
        logger.info(f"Adding {len(chunks)} chunks to Qdrant")
        add_chunks(chunks)
        
        JOB_STATUS[job_id] = {"status": "success", "progress": 100, "message": "Ingestion complete"}
        logger.info(f"Successfully ingested {filename}")
    except Exception as e:
        JOB_STATUS[job_id] = {"status": "error", "progress": 0, "message": str(e)}
        logger.error(f"Failed to ingest {filename}: {e}", exc_info=True)

@router.post("/upload", response_class=JSONResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection: str = Form("general"),
    admin: User = Depends(require_admin),
):
    """Upload a document and trigger re-indexing."""
    try:
        # Create a temp directory for uploads
        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        filename = file.filename.replace(" ", "_") if file.filename else "unknown.pdf"
        file_path = upload_dir / filename

        # Generate a job ID
        job_id = str(uuid.uuid4())

        logger.info(f"Uploading file: {filename}")
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Trigger background ingestion
        background_tasks.add_task(process_and_ingest, job_id, str(file_path), filename, collection)

        return {"status": "success", "message": f"'{filename}' uploaded successfully. Ingestion started.", "job_id": job_id}
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

@router.get("/status/{job_id}")
async def get_ingestion_status(job_id: str, admin: User = Depends(require_admin)):
    """Get the status of an ingestion job."""
    if job_id not in JOB_STATUS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOB_STATUS[job_id]
