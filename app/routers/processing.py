"""Processing control API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.models import get_db, Project
from app.services import LLMService
from app.utils import decrypt_api_key
from app.routers.websocket import manager as websocket_manager

router = APIRouter()


# Pydantic models
class ProcessingConfig(BaseModel):
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    worker_count: int = 3
    chapters_per_batch: int = 3  # Number of chapters to edit together for consistency


class TestConnectionRequest(BaseModel):
    api_endpoint: str
    api_key: str
    model: str = "gpt-4"


@router.post("/projects/{project_id}/process")
async def start_processing(
    project_id: int,
    config: ProcessingConfig,
    db: AsyncSession = Depends(get_db),
):
    """
    Start processing chapters for a project.
    """
    # Get project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if LLM is configured
    if not project.llm_settings:
        raise HTTPException(
            status_code=400, detail="LLM configuration not set for this project"
        )

    # Check if already processing
    if project.processing_status == "processing":
        raise HTTPException(status_code=400, detail="Project is already being processed")

    # Import here to avoid circular imports
    from app.services.processing_service import ProcessingService

    # Create WebSocket callback function
    async def websocket_callback(message: dict):
        """Broadcast updates to WebSocket clients."""
        await websocket_manager.broadcast_to_project(project_id, message)

    # Create processing service with WebSocket callback
    processing_service = ProcessingService(db, project_id, websocket_callback)

    # Determine end chapter
    from app.models import Chapter

    if config.end_chapter is None:
        result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number.desc())
        )
        last_chapter = result.scalars().first()
        end_chapter = last_chapter.chapter_number if last_chapter else 1
    else:
        end_chapter = config.end_chapter

    # Start processing
    try:
        job = await processing_service.start_processing(
            start_chapter=config.start_chapter,
            end_chapter=end_chapter,
            worker_count=config.worker_count,
            chapters_per_batch=config.chapters_per_batch,
        )

        return {
            "message": "Processing started",
            "job_id": job.id,
            "start_chapter": config.start_chapter,
            "end_chapter": end_chapter,
            "worker_count": config.worker_count,
            "chapters_per_batch": config.chapters_per_batch,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")


@router.post("/projects/{project_id}/pause")
async def pause_processing(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Pause processing for a project.
    """
    # Get project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.processing_status != "processing":
        raise HTTPException(status_code=400, detail="Project is not currently processing")

    # Import here to avoid circular imports
    from app.services.processing_service import ProcessingService

    # Create processing service
    processing_service = ProcessingService(db, project_id)

    # Pause processing
    await processing_service.pause_processing()

    return {"message": "Processing paused"}


@router.post("/projects/{project_id}/resume")
async def resume_processing(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Resume processing for a project.
    """
    # Get project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.processing_status != "paused":
        raise HTTPException(status_code=400, detail="Project is not paused")

    # Import here to avoid circular imports
    from app.services.processing_service import ProcessingService

    # Create processing service
    processing_service = ProcessingService(db, project_id)

    # Resume processing
    await processing_service.resume_processing()

    return {"message": "Processing resumed"}


@router.post("/projects/{project_id}/stop")
async def stop_processing(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Stop processing for a project.
    """
    # Get project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.processing_status not in ["processing", "paused"]:
        raise HTTPException(status_code=400, detail="Project is not currently processing")

    # Import here to avoid circular imports
    from app.services.processing_service import ProcessingService

    # Create processing service
    processing_service = ProcessingService(db, project_id)

    # Stop processing
    await processing_service.stop_processing()

    return {"message": "Processing stopped"}


@router.post("/test-llm-connection")
async def test_llm_connection(request: TestConnectionRequest):
    """
    Test LLM API connection.
    """
    try:
        result = await LLMService.test_connection(
            api_endpoint=request.api_endpoint,
            api_key=request.api_key,
            model=request.model,
        )

        return result

    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/projects/{project_id}/export")
async def export_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Export edited ePub file.
    """
    from fastapi.responses import FileResponse
    from app.services import EPubService
    from app.models import Chapter

    # Get project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all completed chapters
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .where(Chapter.processing_status == "completed")
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    if not chapters:
        raise HTTPException(
            status_code=400, detail="No completed chapters to export"
        )

    try:
        # Prepare edited chapters dictionary
        from app.utils import FileManager
        from app.services.processing_service import ProcessingService
        import logging

        logger = logging.getLogger(__name__)

        edited_chapters = {}
        for chapter in chapters:
            edit_data = FileManager.load_chapter_edits(
                project_id, chapter.chapter_number
            )
            logger.info(f"Chapter {chapter.chapter_number}: edit_data keys = {list(edit_data.keys()) if edit_data else 'None'}")

            if edit_data and "edited_lines" in edit_data and "original_xhtml" in edit_data:
                edited_lines = edit_data["edited_lines"]
                original_xhtml = edit_data["original_xhtml"]

                logger.info(f"Chapter {chapter.chapter_number}: {len(edited_lines)} edited lines, original_xhtml length = {len(original_xhtml)}")

                # If edited_lines is empty, use original XHTML unchanged
                if not edited_lines:
                    logger.info(f"Chapter {chapter.chapter_number}: No edited lines, using original XHTML")
                    edited_chapters[chapter.chapter_number] = original_xhtml
                    continue

                # Reconstruct XHTML from edited lines
                edited_text = '\n'.join(edited_lines)
                logger.info(f"Chapter {chapter.chapter_number}: edited_text length = {len(edited_text)}")

                edited_xhtml = ProcessingService._wrap_body_content(
                    edited_text,
                    original_xhtml
                )
                logger.info(f"Chapter {chapter.chapter_number}: reconstructed XHTML length = {len(edited_xhtml)}")
                logger.info(f"Chapter {chapter.chapter_number}: XHTML preview = {edited_xhtml[:200]}...")

                edited_chapters[chapter.chapter_number] = edited_xhtml

        if not edited_chapters:
            raise HTTPException(status_code=400, detail="No edited content found")

        # Generate output path
        output_path = FileManager.get_output_epub_path(
            project_id, f"{project.name}_edited.epub"
        )

        # Reassemble ePub
        EPubService.reassemble_epub(
            original_epub_path=project.original_file_path,
            output_epub_path=output_path,
            edited_chapters=edited_chapters,
        )

        # Return file
        return FileResponse(
            path=output_path,
            media_type="application/epub+zip",
            filename=f"{project.name}_edited.epub",
        )

    except Exception as e:
        import traceback
        logger.error(f"Export failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to export: {str(e)}")
