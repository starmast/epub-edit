"""Project management API endpoints."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.models import get_db, Project, Chapter
from app.services import EPubService, TokenService
from app.utils import FileManager, encrypt_api_key, mask_api_key

router = APIRouter()


# Pydantic models
class ProjectCreate(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    metadata: Optional[dict]
    created_at: str
    updated_at: Optional[str]
    processing_status: str
    chapter_count: int = 0

    class Config:
        from_attributes = True


class LLMConfig(BaseModel):
    api_endpoint: str
    api_key: str
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 4096
    system_prompt: Optional[str] = None


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project by uploading an ePub file.
    """
    # Validate file extension
    if not file.filename.endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only .epub files are allowed")

    # Read file content
    content = await file.read()

    # Create project
    project_name = name or file.filename.replace(".epub", "")
    project = Project(name=project_name, original_file_path="", processing_status="idle")

    db.add(project)
    await db.commit()
    await db.refresh(project)

    try:
        # Save ePub file
        epub_path = FileManager.save_epub(project.id, content, file.filename)

        # Update project with file path
        project.original_file_path = epub_path

        # Extract metadata
        metadata = EPubService.extract_metadata(epub_path)
        project.book_metadata = metadata

        # Extract chapters
        chapters_data = EPubService.extract_chapters(epub_path)

        # Create token service
        token_service = TokenService()

        # Save chapters to database and files
        for chapter_data in chapters_data:
            # Save chapter content to file
            chapter_path = FileManager.save_chapter_content(
                project.id,
                chapter_data["chapter_number"],
                chapter_data["html_content"],
            )

            # Count tokens
            token_count = token_service.count_tokens(chapter_data["text_content"])

            # Create chapter record
            chapter = Chapter(
                project_id=project.id,
                chapter_number=chapter_data["chapter_number"],
                title=chapter_data["title"],
                original_content_path=chapter_path,
                token_count=token_count,
                word_count=chapter_data["word_count"],
                processing_status="not_started",
            )

            db.add(chapter)

        await db.commit()
        await db.refresh(project)

        # Get chapter count
        result = await db.execute(
            select(Chapter).where(Chapter.project_id == project.id)
        )
        chapters = result.scalars().all()

        return ProjectResponse(
            id=project.id,
            name=project.name,
            metadata=project.book_metadata,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat() if project.updated_at else None,
            processing_status=project.processing_status,
            chapter_count=len(chapters),
        )

    except Exception as e:
        # Rollback and delete project if extraction fails
        await db.execute(delete(Project).where(Project.id == project.id))
        await db.commit()

        # Clean up files
        FileManager.delete_project(project.id)

        raise HTTPException(status_code=500, detail=f"Failed to process ePub: {str(e)}")


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """
    List all projects.
    """
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()

    # Get chapter counts
    response = []
    for project in projects:
        result = await db.execute(
            select(Chapter).where(Chapter.project_id == project.id)
        )
        chapters = result.scalars().all()

        response.append(
            ProjectResponse(
                id=project.id,
                name=project.name,
                metadata=project.book_metadata,
                created_at=project.created_at.isoformat(),
                updated_at=project.updated_at.isoformat()
                if project.updated_at
                else None,
                processing_status=project.processing_status,
                chapter_count=len(chapters),
            )
        )

    return response


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a specific project.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get chapter count
    result = await db.execute(
        select(Chapter).where(Chapter.project_id == project.id)
    )
    chapters = result.scalars().all()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        metadata=project.book_metadata,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
        processing_status=project.processing_status,
        chapter_count=len(chapters),
    )


@router.delete("/projects/{project_id}")
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Delete a project and all associated data.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Manually delete chapters first (foreign key doesn't cascade)
    await db.execute(delete(Chapter).where(Chapter.project_id == project_id))

    # Delete processing jobs
    from app.models import ProcessingJob
    await db.execute(delete(ProcessingJob).where(ProcessingJob.project_id == project_id))

    # Delete project
    await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()

    # Delete files
    FileManager.delete_project(project_id)

    return {"message": "Project deleted successfully"}


@router.put("/projects/{project_id}/llm-config")
async def update_llm_config(
    project_id: int,
    config: LLMConfig,
    db: AsyncSession = Depends(get_db),
):
    """
    Update LLM configuration for a project.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Encrypt API key
    encrypted_key = encrypt_api_key(config.api_key)

    # Update LLM settings
    from app.services.llm_service import SystemPrompts

    project.llm_settings = {
        "api_endpoint": config.api_endpoint,
        "encrypted_api_key": encrypted_key,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "system_prompt": config.system_prompt or SystemPrompts.DEFAULT,
    }

    await db.commit()

    return {
        "message": "LLM configuration updated",
        "masked_api_key": mask_api_key(config.api_key),
    }


@router.get("/projects/{project_id}/llm-config")
async def get_llm_config(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get LLM configuration for a project (with masked API key).
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.llm_settings:
        return {"configured": False}

    # Return config with masked key
    config = dict(project.llm_settings)
    if "encrypted_api_key" in config:
        from app.utils import decrypt_api_key

        decrypted_key = decrypt_api_key(config["encrypted_api_key"])
        config["masked_api_key"] = mask_api_key(decrypted_key)
        del config["encrypted_api_key"]

    config["configured"] = True

    return config
